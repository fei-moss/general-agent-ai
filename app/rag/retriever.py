"""RAG 检索编排。

组合 chunker + embedder + vector_store,提供:
- ingest(docs): 分块 -> 向量化 -> 入库。
- retrieve(query, top_k): 向量化查询 -> 检索 -> 返回带 score 的片段。

内置:查询级 LRU 缓存、检索超时、异常/空结果降级(返回空并标记 degraded)。
全链路在 HashEmbedder + InMemoryVectorStore 下确定性、零外部依赖可运行。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections import OrderedDict
from dataclasses import dataclass, field

from app.core.config import Settings, get_settings
from app.core.interfaces import Embedder, VectorStore
from app.core.logging import get_logger, log_with_fields
from app.rag.chunker import chunk_text
from app.rag.embedder import get_embedder
from app.rag.vector_store import get_vector_store

logger = get_logger(__name__)

# 缓存与超时默认值
DEFAULT_CACHE_SIZE = 256
DEFAULT_RETRIEVE_TIMEOUT_S = 10.0


@dataclass(frozen=True)
class RetrievedChunk:
    """检索命中的片段。

    属性:
        doc_id: 来源文档 id。
        text: 片段文本。
        score: 相似度分数(越大越相似)。
        meta: 透传的元数据。
    """

    doc_id: str
    text: str
    score: float
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalResult:
    """一次检索的结果包。

    属性:
        chunks: 命中片段(可能为空)。
        degraded: 是否发生降级(超时/异常/库空)。
        reason: 降级原因(未降级为 None)。
    """

    chunks: list[RetrievedChunk]
    degraded: bool = False
    reason: str | None = None


def _query_key(query: str, top_k: int) -> str:
    """构造缓存键(查询内容 + top_k)。"""
    digest = hashlib.md5(query.encode("utf-8")).hexdigest()
    return f"{digest}:{top_k}"


class RAGRetriever:
    """检索编排器,封装分块、向量化、入库与检索降级。"""

    def __init__(
        self,
        embedder: Embedder | None = None,
        store: VectorStore | None = None,
        settings: Settings | None = None,
        cache_size: int = DEFAULT_CACHE_SIZE,
        timeout_s: float = DEFAULT_RETRIEVE_TIMEOUT_S,
    ) -> None:
        """初始化。未显式传入的依赖经各自工厂创建。"""
        self._settings = settings or get_settings()
        self._embedder = embedder or get_embedder(self._settings)
        self._store = store or get_vector_store(self._settings)
        self._cache_size = max(cache_size, 0)
        self._timeout_s = timeout_s
        self._cache: OrderedDict[str, RetrievalResult] = OrderedDict()

    async def ingest(self, docs: list[dict]) -> int:
        """摄取文档:分块 -> 向量化 -> 入库。

        参数:
            docs: 每个 doc 形如 {"id"?: str, "text": str, "meta"?: dict}。
                  缺 id 时按内容哈希生成;缺 text 的 doc 跳过。

        返回:
            实际入库的片段数。

        异常:
            向量化或入库的底层异常向上抛出(摄取属写路径,不静默降级)。
        """
        records = self._build_chunk_records(docs)
        if not records:
            return 0
        texts = [r["text"] for r in records]
        vectors = await self._embedder.embed(texts)
        for record, vector in zip(records, vectors):
            record["vector"] = vector
        await self._store.add(records)
        # 入库后缓存可能失效,清空以避免陈旧命中
        self._cache.clear()
        log_with_fields(
            logger, logging.INFO, "RAG ingest 完成", chunks=len(records)
        )
        return len(records)

    def _build_chunk_records(self, docs: list[dict]) -> list[dict]:
        """将文档展开为可入库的片段记录列表。"""
        records: list[dict] = []
        for doc in docs:
            text = (doc.get("text") or "").strip()
            if not text:
                continue
            base_id = doc.get("id") or hashlib.md5(text.encode("utf-8")).hexdigest()
            meta = doc.get("meta") or {}
            for chunk in chunk_text(text):
                records.append(
                    {
                        "id": f"{base_id}:{chunk.index}",
                        "text": chunk.text,
                        "meta": {**meta, "doc_id": base_id, "chunk": chunk.index},
                    }
                )
        return records

    async def retrieve(self, query: str, top_k: int | None = None) -> RetrievalResult:
        """检索与查询相关的片段,带缓存、超时与降级。

        参数:
            query: 查询文本。
            top_k: 返回数量,缺省取 settings.retrieval_top_k。

        返回:
            RetrievalResult;任何异常/超时/空结果均降级为标记结果而非抛错。
        """
        k = top_k if top_k is not None else self._settings.retrieval_top_k
        if not query or not query.strip() or k <= 0:
            return RetrievalResult(chunks=[], degraded=True, reason="empty_query")

        key = _query_key(query, k)
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        result = await self._retrieve_uncached(query, k)
        self._cache_put(key, result)
        return result

    async def _retrieve_uncached(self, query: str, k: int) -> RetrievalResult:
        """无缓存检索,统一处理超时与异常降级。"""
        try:
            return await asyncio.wait_for(
                self._do_retrieve(query, k), timeout=self._timeout_s
            )
        except asyncio.TimeoutError:
            log_with_fields(
                logger, logging.WARNING, "RAG 检索超时降级", timeout_s=self._timeout_s
            )
            return RetrievalResult(chunks=[], degraded=True, reason="timeout")
        except Exception as exc:  # noqa: BLE001 — 检索失败降级,保证主流程不崩
            log_with_fields(
                logger, logging.ERROR, "RAG 检索异常降级", error=str(exc)
            )
            return RetrievalResult(chunks=[], degraded=True, reason="error")

    async def _do_retrieve(self, query: str, k: int) -> RetrievalResult:
        """执行实际向量检索并映射为结果片段。"""
        query_vec = (await self._embedder.embed([query]))[0]
        hits = await self._store.search(query_vec, k)
        if not hits:
            return RetrievalResult(chunks=[], degraded=True, reason="empty_result")
        chunks = [
            RetrievedChunk(
                doc_id=doc.get("meta", {}).get("doc_id", doc.get("id", "")),
                text=doc.get("text", ""),
                score=score,
                meta=doc.get("meta", {}),
            )
            for doc, score in hits
        ]
        return RetrievalResult(chunks=chunks, degraded=False, reason=None)

    def _cache_get(self, key: str) -> RetrievalResult | None:
        """LRU 读取:命中则移到队尾。"""
        if self._cache_size == 0 or key not in self._cache:
            return None
        self._cache.move_to_end(key)
        return self._cache[key]

    def _cache_put(self, key: str, value: RetrievalResult) -> None:
        """LRU 写入:超量则淘汰最久未用项。降级结果不缓存,便于恢复后重试。"""
        if self._cache_size == 0 or value.degraded:
            return
        self._cache[key] = value
        self._cache.move_to_end(key)
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
