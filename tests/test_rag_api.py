from __future__ import annotations

import pytest
from fastapi import HTTPException

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
