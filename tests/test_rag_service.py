from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from app.core.config import Settings


class _FakeKnowledgeBaseRepo:
    def __init__(self, *, status: str = "ACTIVE") -> None:
        self.status = status
        self.calls: list[tuple[str, str]] = []

    async def get_for_user(self, knowledge_base_id: str, user_id: str) -> Any:
        self.calls.append((knowledge_base_id, user_id))
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
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def search(
        self, query_vec: list[float], top_k: int, **filters: Any
    ) -> list[tuple[dict[str, Any], float]]:
        self.calls.append(filters)
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


class _FakeDocumentRepo:
    def __init__(self) -> None:
        self.statuses: list[tuple[str, str, str | None]] = []

    async def get(self, document_id: str) -> Any:
        return SimpleNamespace(
            id=document_id,
            knowledge_base_id="kb_1",
            owner_user_id="user_1",
            raw_content="World Cup forecast guidance must separate evidence, probabilities, and no-bet conditions.",
            mime_type="text/plain",
            source_uri="manual://world-cup-forecast/safety",
            meta={
                "doc_id": "worldcup_forecast_safety",
                "section": "forecast_safety",
            },
        )

    async def update_status(
        self,
        document_id: str,
        status: Any,
        *,
        error_message: str | None = None,
    ) -> Any:
        value = status.value if hasattr(status, "value") else str(status)
        self.statuses.append((document_id, value, error_message))
        return SimpleNamespace(id=document_id, status=status)


class _FakeIngestionJobRepo:
    def __init__(self) -> None:
        self.statuses: list[tuple[str, str, str | None]] = []

    async def update_status(
        self,
        job_id: str,
        status: Any,
        *,
        error_message: str | None = None,
    ) -> Any:
        value = status.value if hasattr(status, "value") else str(status)
        self.statuses.append((job_id, value, error_message))
        return SimpleNamespace(id=job_id, status=status)


class _CapturingVectorStore:
    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []

    async def add(self, docs: list[dict[str, Any]]) -> None:
        self.docs.extend(docs)


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


async def test_query_service_uses_internal_owner_but_logs_real_requester():
    from app.rag.service import RAGQueryService

    kb_repo = _FakeKnowledgeBaseRepo()
    log_repo = _FakeRetrievalLogRepo()
    vector_store = _FakeVectorStore()
    service = RAGQueryService(
        knowledge_base_repo=kb_repo,
        retrieval_log_repo=log_repo,
        embedder=_FakeEmbedder(),
        vector_store=vector_store,
        settings=Settings(_env_file=None, rag_query_timeout_ms=1000, embedding_dim=2),
    )

    response = await service.query(
        user_id="alice.internal",
        owner_user_id="rag-admin",
        knowledge_base_id="kb_internal",
        query="DockerHost 怎么部署?",
        top_k=1,
        agent_run_id="run_1",
        conversation_id="conv_1",
    )

    assert response.degraded is False
    assert kb_repo.calls == [("kb_internal", "rag-admin")]
    assert vector_store.calls[0]["owner_user_id"] == "rag-admin"
    assert log_repo.records[0]["user_id"] == "alice.internal"
    assert log_repo.records[0]["knowledge_base_id"] == "kb_internal"


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


async def test_ingestion_preserves_source_doc_id_in_chunk_metadata():
    from app.rag.service import RAGIngestionService

    vector_store = _CapturingVectorStore()
    service = RAGIngestionService(
        document_repo=_FakeDocumentRepo(),
        job_repo=_FakeIngestionJobRepo(),
        embedder=_FakeEmbedder(),
        vector_store=vector_store,
        settings=Settings(
            _env_file=None,
            embedding_provider="gemini",
            embedding_model="gemini-embedding-2",
            embedding_dim=2,
            rag_chunk_size=512,
            rag_chunk_overlap=80,
        ),
    )

    chunk_count = await service.ingest_document(
        job_id="ragjob_1",
        document_id="doc_db_1",
    )

    assert chunk_count == 1
    metadata = vector_store.docs[0]["metadata"]
    assert metadata["doc_id"] == "worldcup_forecast_safety"
    assert metadata["db_document_id"] == "doc_db_1"
    assert metadata["source_uri"] == "manual://world-cup-forecast/safety"
