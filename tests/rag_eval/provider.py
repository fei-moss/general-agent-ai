from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_CORPUS_PATH = Path(__file__).with_name("corpus.jsonl")
_RETRIEVER_CACHE: dict[tuple[Any, ...], Any] = {}


def call_api(prompt: str, options: dict[str, Any] | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Promptfoo Python provider entrypoint."""
    options = options or {}
    context = context or {}
    config = options.get("config") or {}
    vars_ = context.get("vars") or {}
    query = str(vars_.get("query") or prompt or "").strip()
    top_k = int(vars_.get("top_k") or config.get("top_k") or 3)
    language = str(vars_.get("language") or "").strip()
    metadata_filters = {"language": language} if language else {}
    remote_base_url = str(os.getenv("RAG_EVAL_BASE_URL") or "").strip()
    if remote_base_url:
        output = asyncio.run(
            _run_remote_retrieval(
                query=query,
                top_k=top_k,
                base_url=remote_base_url,
                knowledge_base_id=str(
                    os.getenv("RAG_EVAL_KNOWLEDGE_BASE_ID") or ""
                ).strip(),
                admin_id=_remote_admin_id(),
                metadata_filters=metadata_filters,
                timeout_s=float(_config_value(config, "timeout_s", "30")),
            )
        )
    else:
        corpus_path = _resolve_path(config.get("corpus_path") or DEFAULT_CORPUS_PATH)
        output = asyncio.run(
            _run_retrieval(
                query=query,
                top_k=top_k,
                corpus_path=corpus_path,
                config=config,
                metadata_filters=metadata_filters,
            )
        )
    return {"output": json.dumps(output, ensure_ascii=False)}


async def _run_remote_retrieval(
    *,
    query: str,
    top_k: int,
    base_url: str,
    knowledge_base_id: str,
    admin_id: str,
    metadata_filters: dict[str, str],
    timeout_s: float,
    transport: Any | None = None,
) -> dict[str, Any]:
    """Run Promptfoo retrieval through the deployed pgvector/Gemini path."""
    if not knowledge_base_id:
        raise ValueError("RAG_EVAL_KNOWLEDGE_BASE_ID is required for remote retrieval")
    if not admin_id:
        raise ValueError("RAG administrator identity is required for remote retrieval")
    import httpx

    async with httpx.AsyncClient(timeout=timeout_s, transport=transport) as client:
        response = await client.post(
            f"{base_url.rstrip('/')}/rag/query",
            headers={"Authorization": f"Bearer {admin_id}"},
            json={
                "knowledge_base_id": knowledge_base_id,
                "query": query,
                "top_k": top_k,
                "filters": metadata_filters or None,
                "strict": True,
            },
        )
    response.raise_for_status()
    payload = response.json()
    hits = []
    for index, chunk in enumerate(payload.get("chunks") or []):
        metadata = chunk.get("metadata") or {}
        citation = chunk.get("citation") or {}
        hits.append(
            {
                "rank": index + 1,
                "doc_id": metadata.get("doc_id"),
                "score": chunk.get("score"),
                "source": citation.get("source_uri") or metadata.get("source"),
                "preview": str(chunk.get("content") or "")[:240],
            }
        )
    return {
        "query": query,
        "degraded": bool(payload.get("degraded")),
        "reason": payload.get("reason"),
        "top_k": top_k,
        "hits": hits,
    }


@lru_cache(maxsize=1)
def _remote_admin_id() -> str:
    configured = str(os.getenv("RAG_EVAL_ADMIN_ID") or "").strip()
    if configured:
        return configured
    service = str(
        os.getenv("RAG_EVAL_ADMIN_KEYCHAIN_SERVICE")
        or "general-agent-ai-rag-admin-id"
    ).strip()
    completed = subprocess.run(
        ["security", "find-generic-password", "-s", service, "-w"],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


async def _run_retrieval(
    query: str,
    top_k: int,
    corpus_path: Path,
    config: dict[str, Any],
    metadata_filters: dict[str, str] | None = None,
) -> dict[str, Any]:
    retriever = await _build_retriever(
        str(corpus_path),
        _settings_key(config),
        metadata_filters=metadata_filters or {},
    )
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


async def _build_retriever(
    corpus_path: str,
    settings_key: tuple[tuple[str, str], ...],
    *,
    metadata_filters: dict[str, str],
):
    from app.core.config import Settings
    from app.rag.retriever import RAGRetriever

    path = Path(corpus_path)
    stat = path.stat()
    filter_key = tuple(sorted(metadata_filters.items()))
    cache_key = (str(path.resolve()), stat.st_mtime_ns, stat.st_size, settings_key, filter_key)
    cached = _RETRIEVER_CACHE.get(cache_key)
    if cached is not None:
        return cached

    config = dict(settings_key)
    settings = Settings(
        _env_file=None,
        embedding_provider=_config_value(config, "embedding_provider", "hash"),
        embedding_model=_config_value(config, "embedding_model", "hash"),
        embedding_dim=int(_config_value(config, "embedding_dim", "1536")),
        rag_vector_store="memory",
        rag_chunk_size=int(_config_value(config, "rag_chunk_size", "512")),
        rag_chunk_overlap=int(_config_value(config, "rag_chunk_overlap", "80")),
        retrieval_top_k=int(_config_value(config, "retrieval_top_k", "3")),
    )
    retriever = RAGRetriever(settings=settings, timeout_s=float(_config_value(config, "timeout_s", "30")))
    docs = _filter_corpus_docs(_load_corpus(path), metadata_filters)
    if not docs:
        raise ValueError(f"RAG eval corpus has no documents for filters: {metadata_filters}")
    await _ingest_corpus(
        retriever,
        docs,
        batch_size=int(_config_value(config, "ingest_batch_size", "20")),
    )
    _RETRIEVER_CACHE[cache_key] = retriever
    return retriever


async def _ingest_corpus(retriever: Any, docs: list[dict[str, Any]], *, batch_size: int) -> int:
    """Ingest eval documents in bounded batches so provider batch limits are respected."""
    if batch_size <= 0:
        raise ValueError("ingest_batch_size must be positive")
    ingested = 0
    for start in range(0, len(docs), batch_size):
        ingested += await retriever.ingest(docs[start : start + batch_size])
    return ingested


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


def _filter_corpus_docs(
    docs: list[dict[str, Any]], metadata_filters: dict[str, str]
) -> list[dict[str, Any]]:
    if not metadata_filters:
        return docs
    return [
        doc
        for doc in docs
        if all((doc.get("meta") or {}).get(key) == value for key, value in metadata_filters.items())
    ]


def _settings_key(config: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    keys = [
        "embedding_provider",
        "embedding_model",
        "embedding_dim",
        "rag_chunk_size",
        "rag_chunk_overlap",
        "retrieval_top_k",
        "timeout_s",
        "ingest_batch_size",
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
