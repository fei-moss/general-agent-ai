from __future__ import annotations


def test_rag_router_is_registered_on_fastapi_app():
    from app.api.main import create_app

    app = create_app()
    paths = {route.path for route in app.routes}

    assert "/rag/knowledge-bases" in paths
    assert "/rag/documents" in paths
    assert "/rag/query" in paths
