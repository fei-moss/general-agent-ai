from __future__ import annotations

from pathlib import Path

from sqlalchemy import UniqueConstraint


def test_rag_orm_models_expose_persistent_contract():
    from app.core.enums import (
        KnowledgeBaseStatus,
        RAGDocumentStatus,
        RAGIngestionJobStatus,
    )
    from app.core.models import (
        KnowledgeBase,
        RAGDocument,
        RAGDocumentChunk,
        RAGIngestionJob,
        RAGRetrievalLog,
    )

    assert KnowledgeBase.__tablename__ == "knowledge_base"
    assert RAGDocument.__tablename__ == "rag_document"
    assert RAGDocumentChunk.__tablename__ == "rag_document_chunk"
    assert RAGIngestionJob.__tablename__ == "rag_ingestion_job"
    assert RAGRetrievalLog.__tablename__ == "rag_retrieval_log"
    assert KnowledgeBaseStatus.ACTIVE.value == "ACTIVE"
    assert RAGDocumentStatus.EMBEDDED.value == "EMBEDDED"
    assert RAGIngestionJobStatus.CANCELLED.value == "CANCELLED"

    document_unique_columns = {
        tuple(constraint.columns.keys())
        for constraint in RAGDocument.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    chunk_unique_columns = {
        tuple(constraint.columns.keys())
        for constraint in RAGDocumentChunk.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("knowledge_base_id", "content_hash") in document_unique_columns
    assert ("document_id", "index_version", "chunk_index") in chunk_unique_columns
    assert {"raw_content", "metadata", "status"}.issubset(
        set(RAGDocument.__table__.columns.keys())
    )
    assert {"matched_chunk_ids", "scores", "degraded", "reason"}.issubset(
        set(RAGRetrievalLog.__table__.columns.keys())
    )


def test_init_sql_enables_pgvector_and_rag_tables():
    sql = Path("app/db/init.sql").read_text(encoding="utf-8").lower()

    assert "create extension if not exists vector" in sql
    assert "create table if not exists knowledge_base" in sql
    assert "create table if not exists rag_document" in sql
    assert "create table if not exists rag_document_chunk" in sql
    assert "embedding vector(" in sql
    assert "create table if not exists rag_retrieval_log" in sql
