"""向量存储与检索实现。

提供:
- InMemoryVectorStore: numpy 余弦相似度的进程内向量库,线程安全,top_k 检索。
- PgVectorStore: 基于 pgvector 的实现骨架(预留,默认不启用)。

工厂 get_vector_store() 默认返回内存实现,保证零外部依赖跑通。
"""

from __future__ import annotations

import threading
import json
from typing import Any

import numpy as np
from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.core.interfaces import VectorStore

_EPS = 1e-12


def _to_matrix(vectors: list[list[float]]) -> np.ndarray:
    """将向量列表转为二维矩阵(float64)。"""
    return np.asarray(vectors, dtype=np.float64)


def _normalize_rows(mat: np.ndarray) -> np.ndarray:
    """对矩阵按行 L2 归一化,零向量保持为零。"""
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.where(norms < _EPS, 1.0, norms)
    return mat / norms


class InMemoryVectorStore:
    """进程内向量库,用 numpy 计算余弦相似度。

    内部以 dict 保存 doc(键为 doc["id"]),检索时按需组装矩阵批量计算。
    所有读写均加锁,保证多线程/多协程并发安全。
    """

    def __init__(self) -> None:
        """初始化空库。"""
        self._lock = threading.Lock()
        self._docs: dict[str, dict[str, Any]] = {}

    @property
    def size(self) -> int:
        """当前文档数量。"""
        with self._lock:
            return len(self._docs)

    async def add(self, docs: list[dict[str, Any]]) -> None:
        """新增/覆盖文档。

        参数:
            docs: 每个 doc 至少含 id/text/vector。重复 id 覆盖旧值。

        异常:
            ValueError: 缺少必要字段时抛出。
        """
        for doc in docs:
            if "id" not in doc or "vector" not in doc:
                raise ValueError("doc 必须包含 id 与 vector 字段")
        with self._lock:
            for doc in docs:
                self._docs[doc["id"]] = dict(doc)  # 拷贝,避免外部突变

    async def search(
        self, query_vec: list[float], top_k: int, **filters: Any
    ) -> list[tuple[dict[str, Any], float]]:
        """按余弦相似度返回 top_k 个 (doc, score)。

        空库或 top_k<=0 返回空列表。score 范围约 [-1, 1],越大越相似。
        """
        if top_k <= 0:
            return []
        with self._lock:
            if not self._docs:
                return []
            ids = [
                doc_id
                for doc_id, doc in self._docs.items()
                if _matches_filters(doc, filters)
            ]
            if not ids:
                return []
            matrix = _to_matrix([self._docs[i]["vector"] for i in ids])
            snapshot = {i: dict(self._docs[i]) for i in ids}

        query = _to_matrix([query_vec])
        if matrix.shape[1] != query.shape[1]:
            raise ValueError("查询向量维度与库内向量不一致")
        normed = _normalize_rows(matrix)
        q_normed = _normalize_rows(query)[0]
        scores = normed @ q_normed  # (N,) 余弦相似度

        k = min(top_k, len(ids))
        # argpartition 取 top-k 再排序,避免全排序开销
        top_idx = np.argpartition(-scores, k - 1)[:k]
        ordered = top_idx[np.argsort(-scores[top_idx])]
        return [(snapshot[ids[i]], float(scores[i])) for i in ordered]


class PgVectorStore:
    """基于 pgvector 的向量库实现。"""

    def __init__(self, settings: Settings) -> None:
        """记录连接配置。"""
        self._db_url = settings.db_url
        self._dim = settings.embedding_dim
        self._settings = settings

    async def add(self, docs: list[dict[str, Any]]) -> None:
        """写入/覆盖 pgvector chunk 行。"""
        if not docs:
            return
        from app.db.session import async_session_factory

        stmt = text(
            """
            INSERT INTO rag_document_chunk (
                id, document_id, knowledge_base_id, owner_user_id, chunk_index,
                content, content_hash, token_count, page_number, section_title,
                metadata, embedding, embedding_provider, embedding_model,
                embedding_dim, index_version
            ) VALUES (
                :id, :document_id, :knowledge_base_id, :owner_user_id, :chunk_index,
                :content, :content_hash, :token_count, :page_number, :section_title,
                CAST(:metadata AS jsonb), CAST(:embedding AS vector),
                :embedding_provider, :embedding_model, :embedding_dim, :index_version
            )
            ON CONFLICT (document_id, index_version, chunk_index)
            DO UPDATE SET
                content = EXCLUDED.content,
                content_hash = EXCLUDED.content_hash,
                token_count = EXCLUDED.token_count,
                page_number = EXCLUDED.page_number,
                section_title = EXCLUDED.section_title,
                metadata = EXCLUDED.metadata,
                embedding = EXCLUDED.embedding,
                embedding_provider = EXCLUDED.embedding_provider,
                embedding_model = EXCLUDED.embedding_model,
                embedding_dim = EXCLUDED.embedding_dim
            """
        )
        async with async_session_factory() as session:
            for doc in docs:
                vector = doc.get("vector") or doc.get("embedding") or []
                if len(vector) != self._dim:
                    raise ValueError("embedding_dimension_mismatch")
                await session.execute(
                    stmt,
                    {
                        "id": doc.get("id") or doc.get("chunk_id"),
                        "document_id": doc["document_id"],
                        "knowledge_base_id": doc["knowledge_base_id"],
                        "owner_user_id": doc["owner_user_id"],
                        "chunk_index": doc["chunk_index"],
                        "content": doc.get("content") or doc.get("text") or "",
                        "content_hash": doc["content_hash"],
                        "token_count": int(doc.get("token_count") or 0),
                        "page_number": doc.get("page_number"),
                        "section_title": doc.get("section_title"),
                        "metadata": json.dumps(
                            doc.get("metadata") or doc.get("meta") or {},
                            ensure_ascii=False,
                        ),
                        "embedding": _vector_literal(vector),
                        "embedding_provider": doc.get("embedding_provider")
                        or self._settings.embedding_provider,
                        "embedding_model": doc.get("embedding_model")
                        or self._settings.embedding_model,
                        "embedding_dim": int(doc.get("embedding_dim") or self._dim),
                        "index_version": doc.get("index_version")
                        or self._settings.rag_index_version,
                    },
                )
            await session.commit()

    async def search(
        self, query_vec: list[float], top_k: int, **filters: Any
    ) -> list[tuple[dict[str, Any], float]]:
        """pgvector 近邻检索。"""
        if top_k <= 0:
            return []
        if len(query_vec) != self._dim:
            raise ValueError("查询向量维度与库内向量不一致")
        from app.db.session import async_session_factory

        metadata_filter = filters.get("filters") or {}
        stmt = text(
            """
            SELECT
                id, document_id, knowledge_base_id, chunk_index, content,
                metadata, page_number, section_title,
                1 - (embedding <=> CAST(:query_vec AS vector)) AS score
            FROM rag_document_chunk
            WHERE owner_user_id = :owner_user_id
              AND knowledge_base_id = :knowledge_base_id
              AND index_version = :index_version
              AND (:metadata_filter = '{}' OR metadata @> CAST(:metadata_filter AS jsonb))
            ORDER BY embedding <=> CAST(:query_vec AS vector)
            LIMIT :top_k
            """
        )
        async with async_session_factory() as session:
            result = await session.execute(
                stmt,
                {
                    "query_vec": _vector_literal(query_vec),
                    "owner_user_id": filters.get("owner_user_id"),
                    "knowledge_base_id": filters.get("knowledge_base_id"),
                    "index_version": filters.get("index_version")
                    or self._settings.rag_index_version,
                    "metadata_filter": json.dumps(
                        metadata_filter, ensure_ascii=False
                    ),
                    "top_k": top_k,
                },
            )
            rows = result.mappings().all()
        output: list[tuple[dict[str, Any], float]] = []
        for row in rows:
            meta = dict(row.get("metadata") or {})
            output.append(
                (
                    {
                        "id": row["id"],
                        "document_id": row["document_id"],
                        "knowledge_base_id": row["knowledge_base_id"],
                        "chunk_index": row["chunk_index"],
                        "content": row["content"],
                        "metadata": meta,
                        "citation": {
                            "source_uri": meta.get("source_uri"),
                            "page": row.get("page_number"),
                            "section": row.get("section_title")
                            or meta.get("section"),
                            "chunk_index": row["chunk_index"],
                        },
                    },
                    float(row["score"]),
                )
            )
        return output


def get_vector_store(settings: Settings | None = None) -> VectorStore:
    """工厂:返回向量库实例。

    默认返回 InMemoryVectorStore(零依赖)。仅当显式配置 pgvector 时返回
    PgVectorStore,避免本地 demo 依赖 Postgres 扩展。
    """
    settings = settings or get_settings()
    if settings.rag_vector_store.strip().lower() == "pgvector":
        return PgVectorStore(settings)
    return InMemoryVectorStore()


def _matches_filters(doc: dict[str, Any], filters: dict[str, Any]) -> bool:
    owner_user_id = filters.get("owner_user_id")
    if owner_user_id and doc.get("owner_user_id") != owner_user_id:
        return False
    knowledge_base_id = filters.get("knowledge_base_id")
    if knowledge_base_id and doc.get("knowledge_base_id") != knowledge_base_id:
        return False
    index_version = filters.get("index_version")
    if index_version and doc.get("index_version") != index_version:
        return False
    metadata_filter = filters.get("filters") or {}
    metadata = doc.get("metadata") or doc.get("meta") or {}
    for key, expected in metadata_filter.items():
        if metadata.get(key) != expected:
            return False
    return True


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(float(item)) for item in vector) + "]"
