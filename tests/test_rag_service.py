from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from app.core.config import Settings


class _FakeKnowledgeBaseRepo:
    def __init__(self, *, status: str = "ACTIVE") -> None:
        self.status = status

    async def get_for_user(self, knowledge_base_id: str, user_id: str) -> Any:
        return SimpleNamespace(
            id=knowledge_base_id,
            owner_user_id=user_id,
            status=self.status,
        )


class _FakeRetrievalLogRepo:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.records.append(kwargs)
        return SimpleNamespace(id="retrlog_1", **kwargs)


class _FakeEmbedder:
    dim = 2

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class _SlowEmbedder(_FakeEmbedder):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        await asyncio.sleep(0.05)
        return await super().embed(texts)


class _FakeVectorStore:
    async def search(
        self, query_vec: list[float], top_k: int, **filters: Any
    ) -> list[tuple[dict[str, Any], float]]:
        return [
            (
                {
                    "id": "chunk_1",
                    "document_id": "doc_1",
                    "knowledge_base_id": filters["knowledge_base_id"],
                    "title": "Deploy",
                    "text": "Use the DockerHost pgvector stack.",
                    "metadata": {"section": "deploy"},
                    "citation": {
                        "source_uri": "manual://deploy",
                        "page": None,
                        "section": "deploy",
                        "chunk_index": 0,
                    },
                },
                0.91,
            )
        ][:top_k]


async def test_query_service_returns_citations_and_writes_retrieval_log():
    from app.rag.service import RAGQueryService

    log_repo = _FakeRetrievalLogRepo()
    service = RAGQueryService(
        knowledge_base_repo=_FakeKnowledgeBaseRepo(),
        retrieval_log_repo=log_repo,
        embedder=_FakeEmbedder(),
        vector_store=_FakeVectorStore(),
        settings=Settings(_env_file=None, rag_query_timeout_ms=1000, embedding_dim=2),
    )

    response = await service.query(
        user_id="user_1",
        knowledge_base_id="kb_1",
        query="How do we deploy?",
        top_k=1,
        agent_run_id="run_1",
        conversation_id="conv_1",
    )

    assert response.degraded is False
    assert response.reason is None
    assert response.chunks[0].chunk_id == "chunk_1"
    assert response.chunks[0].citation.source_uri == "manual://deploy"
    assert log_repo.records[0]["agent_run_id"] == "run_1"
    assert log_repo.records[0]["matched_chunk_ids"] == ["chunk_1"]
    assert log_repo.records[0]["degraded"] is False


async def test_query_service_timeout_degrades_without_raising():
    from app.rag.service import RAGQueryService

    log_repo = _FakeRetrievalLogRepo()
    service = RAGQueryService(
        knowledge_base_repo=_FakeKnowledgeBaseRepo(),
        retrieval_log_repo=log_repo,
        embedder=_SlowEmbedder(),
        vector_store=_FakeVectorStore(),
        settings=Settings(_env_file=None, rag_query_timeout_ms=1, embedding_dim=2),
    )

    response = await service.query(
        user_id="user_1",
        knowledge_base_id="kb_1",
        query="slow query",
        top_k=1,
        agent_run_id="run_1",
        conversation_id="conv_1",
    )

    assert response.degraded is True
    assert response.reason == "timeout"
    assert response.chunks == []
    assert log_repo.records[0]["degraded"] is True
    assert log_repo.records[0]["reason"] == "timeout"
