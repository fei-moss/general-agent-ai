"""向量存储与检索实现。

提供:
- InMemoryVectorStore: numpy 余弦相似度的进程内向量库,线程安全,top_k 检索。
- PgVectorStore: 基于 pgvector 的实现骨架(预留,默认不启用)。

工厂 get_vector_store() 默认返回内存实现,保证零外部依赖跑通。
"""

from __future__ import annotations

import threading
from typing import Any

import numpy as np

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
        self, query_vec: list[float], top_k: int
    ) -> list[tuple[dict[str, Any], float]]:
        """按余弦相似度返回 top_k 个 (doc, score)。

        空库或 top_k<=0 返回空列表。score 范围约 [-1, 1],越大越相似。
        """
        if top_k <= 0:
            return []
        with self._lock:
            if not self._docs:
                return []
            ids = list(self._docs.keys())
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
    """基于 pgvector 的向量库骨架(预留)。

    真实实现需:建表 + ivfflat/hnsw 索引,SQL `ORDER BY embedding <=> :q`
    取近邻。当前仅占位,方法抛 NotImplementedError,避免误用。
    """

    def __init__(self, settings: Settings) -> None:
        """记录连接配置(尚未实现)。"""
        self._db_url = settings.db_url
        self._dim = settings.embedding_dim

    async def add(self, docs: list[dict[str, Any]]) -> None:
        """待实现:写入 pgvector 表。"""
        raise NotImplementedError("PgVectorStore.add 尚未实现")

    async def search(
        self, query_vec: list[float], top_k: int
    ) -> list[tuple[dict[str, Any], float]]:
        """待实现:pgvector 近邻检索。"""
        raise NotImplementedError("PgVectorStore.search 尚未实现")


def get_vector_store(settings: Settings | None = None) -> VectorStore:
    """工厂:返回向量库实例。

    默认返回 InMemoryVectorStore(零依赖)。pgvector 后端待实现,
    暂不通过工厂暴露,确保 demo 可直接运行。
    """
    _ = settings or get_settings()
    return InMemoryVectorStore()
