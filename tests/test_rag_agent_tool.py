from __future__ import annotations

from typing import Any


class _FakeRAGQueryService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def query(self, **kwargs: Any) -> Any:
        from app.core.schemas import CitationOut, KnowledgeSearchResult, RAGQueryResponse

        self.calls.append(kwargs)
        return RAGQueryResponse(
            chunks=[
                KnowledgeSearchResult(
                    chunk_id="chunk_1",
                    document_id="doc_1",
                    knowledge_base_id=kwargs["knowledge_base_id"],
                    title="Guide",
                    content="Use pgvector.",
                    score=0.9,
                    citation=CitationOut(
                        source_uri="manual://guide",
                        page=None,
                        section="setup",
                        chunk_index=0,
                    ),
                    metadata={"section": "setup"},
                )
            ],
            degraded=False,
            reason=None,
            latency_ms=12,
            query_id="retrlog_1",
        )


async def test_retriever_adapter_returns_no_knowledge_base_without_calling_service():
    from app.runtime.adapters import RetrieverAdapter

    service = _FakeRAGQueryService()
    adapter = RetrieverAdapter(
        query_service=service,
        user_id="user_1",
        conversation_id="conv_1",
        agent_run_id="run_1",
        knowledge_base_id=None,
    )

    response = await adapter.retrieve("deployment", top_k=3)

    assert response["chunks"] == []
    assert response["degraded"] is True
    assert response["reason"] == "no_knowledge_base"
    assert service.calls == []


async def test_retriever_adapter_passes_runtime_context_to_query_service():
    from app.runtime.adapters import RetrieverAdapter

    service = _FakeRAGQueryService()
    adapter = RetrieverAdapter(
        query_service=service,
        user_id="user_1",
        conversation_id="conv_1",
        agent_run_id="run_1",
        knowledge_base_id="kb_1",
    )

    response = await adapter.retrieve("deployment", top_k=2)

    assert response["degraded"] is False
    assert response["chunks"][0]["chunk_id"] == "chunk_1"
    assert service.calls[0]["user_id"] == "user_1"
    assert service.calls[0]["conversation_id"] == "conv_1"
    assert service.calls[0]["agent_run_id"] == "run_1"
    assert service.calls[0]["knowledge_base_id"] == "kb_1"
    assert service.calls[0]["top_k"] == 2
