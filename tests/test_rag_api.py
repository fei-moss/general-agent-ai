from __future__ import annotations

import pytest
from fastapi import HTTPException
from types import SimpleNamespace

from app.core.config import Settings


def test_rag_router_is_registered_on_fastapi_app():
    from app.api.main import create_app

    app = create_app()
    paths = {route.path for route in app.routes}

    assert "/rag/knowledge-bases" in paths
    assert "/rag/documents" in paths
    assert "/rag/query" in paths


def test_rag_admin_guard_fails_closed_when_no_admins_are_configured():
    from app.api.routers.rag import _assert_rag_admin

    with pytest.raises(HTTPException) as exc:
        _assert_rag_admin(
            "alice.internal",
            Settings(_env_file=None, rag_admin_user_ids=""),
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "RAG_ADMIN_FORBIDDEN"


def test_rag_admin_guard_allows_only_configured_internal_identities():
    from app.api.routers.rag import _assert_rag_admin

    settings = Settings(
        _env_file=None,
        rag_admin_user_ids="rag-admin, ingestion-agent",
    )

    _assert_rag_admin("rag-admin", settings)
    _assert_rag_admin("ingestion-agent", settings)

    with pytest.raises(HTTPException) as exc:
        _assert_rag_admin("alice.internal", settings)

    assert exc.value.status_code == 403
    assert exc.value.detail == "RAG_ADMIN_FORBIDDEN"


async def test_rag_query_route_rejects_non_admin_before_service_call():
    from app.api.routers.rag import query_knowledge
    from app.core.schemas import RAGQueryRequest

    with pytest.raises(HTTPException) as exc:
        await query_knowledge(
            RAGQueryRequest(knowledge_base_id="kb_internal", query="部署方式"),
            user="alice.internal",
            settings=Settings(_env_file=None, rag_admin_user_ids="rag-admin"),
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "RAG_ADMIN_FORBIDDEN"


async def test_duplicate_pending_document_requeues_after_previous_enqueue_failure(monkeypatch):
    from app.api.routers import rag
    from app.core.enums import RAGDocumentStatus, RAGIngestionJobStatus
    from app.core.schemas import RAGDocumentCreate

    document = SimpleNamespace(
        id="doc-1",
        knowledge_base_id="kb-1",
        owner_user_id="rag-admin",
        status=RAGDocumentStatus.PENDING,
    )
    job = SimpleNamespace(
        id="job-1",
        document_id="doc-1",
        status=RAGIngestionJobStatus.PENDING,
    )
    enqueued: list[tuple[str, str]] = []

    class _DocumentRepo:
        def __init__(self, session):
            pass

        async def create_or_get(self, **kwargs):
            return document, False

    class _JobRepo:
        def __init__(self, session):
            pass

        async def get_latest_for_document(self, document_id):
            return job

        async def mark_dispatched(self, job_id):
            job.dispatch_attempts = 1

    async def _kb(*args, **kwargs):
        return SimpleNamespace(status="ACTIVE")

    monkeypatch.setattr(rag, "RAGDocumentRepository", _DocumentRepo)
    monkeypatch.setattr(rag, "RAGIngestionJobRepository", _JobRepo)
    monkeypatch.setattr(rag, "_get_kb_or_error", _kb)
    monkeypatch.setattr(
        rag,
        "_enqueue_ingestion",
        lambda job_id, document_id: enqueued.append((job_id, document_id)),
    )

    accepted = await rag.create_document(
        RAGDocumentCreate(
            knowledge_base_id="kb-1",
            source_type="manual",
            content="same content",
        ),
        user="rag-admin",
        repos=SimpleNamespace(session=object()),
        settings=Settings(_env_file=None, rag_admin_user_ids="rag-admin"),
    )

    assert accepted.replayed is True
    assert enqueued == [("job-1", "doc-1")]
