from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_CORPUS_PATH = Path(__file__).with_name("corpus.jsonl")
_RETRIEVER_CACHE: dict[tuple[str, int, int, tuple[tuple[str, str], ...]], Any] = {}


def call_api(prompt: str, options: dict[str, Any] | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Promptfoo Python provider entrypoint."""
    options = options or {}
    context = context or {}
    config = options.get("config") or {}
    vars_ = context.get("vars") or {}
    query = str(vars_.get("query") or prompt or "").strip()
    top_k = int(vars_.get("top_k") or config.get("top_k") or 3)
    corpus_path = _resolve_path(config.get("corpus_path") or DEFAULT_CORPUS_PATH)

    output = asyncio.run(_run_retrieval(query=query, top_k=top_k, corpus_path=corpus_path, config=config))
    return {"output": json.dumps(output, ensure_ascii=False)}


async def _run_retrieval(query: str, top_k: int, corpus_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    retriever = await _build_retriever(str(corpus_path), _settings_key(config))
    result = await retriever.retrieve(query, top_k=top_k)
    hits = [
        {
            "rank": index + 1,
            "doc_id": chunk.doc_id,
            "score": chunk.score,
            "source": chunk.meta.get("source"),
            "preview": chunk.text[:240],
        }
        for index, chunk in enumerate(result.chunks)
    ]
    return {
        "query": query,
        "degraded": result.degraded,
        "reason": result.reason,
        "top_k": top_k,
        "hits": hits,
    }


async def _build_retriever(corpus_path: str, settings_key: tuple[tuple[str, str], ...]):
    from app.core.config import Settings
    from app.rag.retriever import RAGRetriever

    path = Path(corpus_path)
    stat = path.stat()
    cache_key = (str(path.resolve()), stat.st_mtime_ns, stat.st_size, settings_key)
    cached = _RETRIEVER_CACHE.get(cache_key)
    if cached is not None:
        return cached

    config = dict(settings_key)
    settings = Settings(
        _env_file=None,
        embedding_provider=_config_value(config, "embedding_provider", "hash"),
        embedding_model=_config_value(config, "embedding_model", "hash"),
        embedding_dim=int(_config_value(config, "embedding_dim", "256")),
        rag_vector_store="memory",
        rag_chunk_size=int(_config_value(config, "rag_chunk_size", "512")),
        rag_chunk_overlap=int(_config_value(config, "rag_chunk_overlap", "80")),
        retrieval_top_k=int(_config_value(config, "retrieval_top_k", "3")),
    )
    retriever = RAGRetriever(settings=settings, timeout_s=float(_config_value(config, "timeout_s", "30")))
    docs = _load_corpus(path)
    await retriever.ingest(docs)
    _RETRIEVER_CACHE[cache_key] = retriever
    return retriever


def _load_corpus(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"RAG eval corpus not found: {path}")
    docs: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not row.get("id") or not row.get("text"):
            raise ValueError(f"invalid corpus row at {path}:{line_no}")
        docs.append({"id": row["id"], "text": row["text"], "meta": row.get("meta") or {}})
    if not docs:
        raise ValueError(f"RAG eval corpus is empty: {path}")
    return docs


def _settings_key(config: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    keys = [
        "embedding_provider",
        "embedding_model",
        "embedding_dim",
        "rag_chunk_size",
        "rag_chunk_overlap",
        "retrieval_top_k",
        "timeout_s",
    ]
    values = {key: str(config[key]) for key in keys if key in config}
    return tuple(sorted(values.items()))


def _config_value(config: dict[str, str], key: str, default: str) -> str:
    env_key = f"RAG_EVAL_{key.upper()}"
    if os.getenv(env_key):
        return os.environ[env_key]
    if key.startswith("embedding_"):
        embedding_env = key.upper()
        if os.getenv(embedding_env):
            return os.environ[embedding_env]
    return str(config.get(key) or default)


def _resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    local_path = Path(__file__).resolve().parent / path
    if local_path.exists():
        return local_path.resolve()
    if path.exists():
        return path.resolve()
    return (REPO_ROOT / path).resolve()
