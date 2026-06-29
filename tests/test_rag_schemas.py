from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError


def test_knowledge_base_schema_trims_and_validates_name():
    from app.core.schemas import KnowledgeBaseCreate

    body = KnowledgeBaseCreate(name="  Project Handbook  ", description="docs")

    assert body.name == "Project Handbook"
    assert body.description == "docs"

    with pytest.raises(ValidationError):
        KnowledgeBaseCreate(name="   ")


def test_rag_document_schema_accepts_text_like_manual_content_only():
    from app.core.schemas import RAGDocumentCreate

    body = RAGDocumentCreate(
        knowledge_base_id="kb_1",
        title="Guide",
        content="# Setup\nUse pgvector.",
        source_type="manual",
        mime_type="text/markdown",
        metadata={"section": "setup"},
    )

    assert body.content.startswith("# Setup")
    assert body.source_type == "manual"

    with pytest.raises(ValidationError):
        RAGDocumentCreate(
            knowledge_base_id="kb_1",
            content="   ",
            source_type="manual",
        )

    with pytest.raises(ValidationError):
        RAGDocumentCreate(
            knowledge_base_id="kb_1",
            content="hello",
            source_type="upload",
        )


def test_rag_query_schema_bounds_top_k_and_strict_mode():
    from app.core.schemas import RAGQueryRequest

    body = RAGQueryRequest(
        knowledge_base_id="kb_1",
        query="How do we deploy?",
        top_k=3,
        strict=True,
    )

    assert body.top_k == 3
    assert body.strict is True

    with pytest.raises(ValidationError):
        RAGQueryRequest(knowledge_base_id="kb_1", query=" ", top_k=3)

    with pytest.raises(ValidationError):
        RAGQueryRequest(knowledge_base_id="kb_1", query="x", top_k=0)


def test_rag_document_out_reads_orm_meta_but_serializes_metadata():
    from app.core.enums import RAGDocumentStatus
    from app.core.schemas import RAGDocumentOut

    now = datetime.now(timezone.utc)
    out = RAGDocumentOut.model_validate(
        SimpleNamespace(
            id="doc_1",
            knowledge_base_id="kb_1",
            owner_user_id="user_1",
            title="Guide",
            source_type="manual",
            source_uri=None,
            mime_type="text/plain",
            status=RAGDocumentStatus.EMBEDDED,
            error_message=None,
            meta={"section": "setup"},
            created_at=now,
            updated_at=now,
        )
    )

    dumped = out.model_dump(mode="json", by_alias=True)

    assert dumped["metadata"] == {"section": "setup"}
    assert "meta" not in dumped
