"""RAG management and query API."""

from __future__ import annotations

import hashlib
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, ReposDep
from app.core.config import Settings, get_settings
from app.core.enums import (
    KnowledgeBaseStatus,
    RAGDocumentStatus,
)
from app.core.ids import _new_id
from app.core.logging import get_logger, log_with_fields
from app.core.schemas import (
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    RAGDocumentAccepted,
    RAGDocumentCreate,
    RAGDocumentOut,
    RAGIngestionJobOut,
    RAGQueryRequest,
    RAGQueryResponse,
)
from app.db.repositories import (
    KnowledgeBaseRepository,
    RAGDocumentRepository,
    RAGIngestionJobRepository,
)
from app.rag.service import RAGQueryError, build_query_service

logger = get_logger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.post(
    "/knowledge-bases",
    status_code=status.HTTP_201_CREATED,
    response_model=KnowledgeBaseOut,
)
async def create_knowledge_base(
    body: KnowledgeBaseCreate,
    user: CurrentUser,
    repos: ReposDep,
    settings: SettingsDep,
) -> Any:
    _assert_rag_admin(user, settings)
    repo = KnowledgeBaseRepository(repos.session)
    return await repo.create(
        owner_user_id=user,
        name=body.name,
        description=body.description,
    )


@router.get("/knowledge-bases", response_model=list[KnowledgeBaseOut])
async def list_knowledge_bases(
    user: CurrentUser, repos: ReposDep, settings: SettingsDep
) -> Any:
    _assert_rag_admin(user, settings)
    repo = KnowledgeBaseRepository(repos.session)
    return await repo.list_for_user(user)


@router.get("/knowledge-bases/{knowledge_base_id}", response_model=KnowledgeBaseOut)
async def get_knowledge_base(
    knowledge_base_id: str,
    user: CurrentUser,
    repos: ReposDep,
    settings: SettingsDep,
) -> Any:
    _assert_rag_admin(user, settings)
    return await _get_kb_or_error(knowledge_base_id, user, repos)


@router.post(
    "/documents",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RAGDocumentAccepted,
)
async def create_document(
    body: RAGDocumentCreate,
    user: CurrentUser,
    repos: ReposDep,
    settings: SettingsDep,
) -> RAGDocumentAccepted:
    _assert_rag_admin(user, settings)
    kb = await _get_kb_or_error(body.knowledge_base_id, user, repos)
    if _status_value(kb.status) != KnowledgeBaseStatus.ACTIVE.value:
        raise HTTPException(status_code=409, detail="KNOWLEDGE_BASE_DISABLED")

    doc_repo = RAGDocumentRepository(repos.session)
    job_repo = RAGIngestionJobRepository(repos.session)
    document, created = await doc_repo.create_or_get(
        document_id=_new_id("doc_"),
        knowledge_base_id=body.knowledge_base_id,
        owner_user_id=user,
        title=body.title,
        source_type=body.source_type,
        source_uri=body.source_uri,
        mime_type=body.mime_type,
        content_hash=_content_hash(body.content),
        raw_content=body.content,
        metadata=body.metadata,
    )
    job = await job_repo.get_latest_for_document(document.id)
    if job is None:
        job = await job_repo.create(
            job_id=_new_id("ragjob_"),
            document_id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            owner_user_id=user,
            payload={"source_type": body.source_type},
        )
    if created:
        _enqueue_ingestion(job.id, document.id)
    return RAGDocumentAccepted(
        document_id=document.id,
        job_id=job.id,
        status=document.status,
        replayed=not created,
    )


@router.get("/documents/{document_id}", response_model=RAGDocumentOut)
async def get_document(
    document_id: str,
    user: CurrentUser,
    repos: ReposDep,
    settings: SettingsDep,
) -> Any:
    _assert_rag_admin(user, settings)
    doc_repo = RAGDocumentRepository(repos.session)
    document = await doc_repo.get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="DOCUMENT_NOT_FOUND")
    if document.owner_user_id != user:
        raise HTTPException(status_code=403, detail="DOCUMENT_FORBIDDEN")
    return _document_out(document)


@router.get("/ingestion-jobs/{job_id}", response_model=RAGIngestionJobOut)
async def get_ingestion_job(
    job_id: str,
    user: CurrentUser,
    repos: ReposDep,
    settings: SettingsDep,
) -> Any:
    _assert_rag_admin(user, settings)
    job_repo = RAGIngestionJobRepository(repos.session)
    job = await job_repo.get_for_user(job_id, user)
    if job is None:
        raise HTTPException(status_code=404, detail="INGESTION_JOB_NOT_FOUND")
    return job


@router.post("/query", response_model=RAGQueryResponse)
async def query_knowledge(
    body: RAGQueryRequest,
    user: CurrentUser,
    settings: SettingsDep,
) -> RAGQueryResponse:
    _assert_rag_admin(user, settings)
    service = build_query_service()
    try:
        return await service.query(
            user_id=user,
            knowledge_base_id=body.knowledge_base_id,
            query=body.query,
            top_k=body.top_k,
            filters=body.filters,
            strict=body.strict,
        )
    except RAGQueryError as exc:
        raise HTTPException(status_code=_strict_status(exc.reason), detail=exc.reason)


async def _get_kb_or_error(knowledge_base_id: str, user: str, repos: ReposDep) -> Any:
    repo = KnowledgeBaseRepository(repos.session)
    kb = await repo.get(knowledge_base_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="KNOWLEDGE_BASE_NOT_FOUND")
    if kb.owner_user_id != user:
        raise HTTPException(status_code=403, detail="KNOWLEDGE_BASE_FORBIDDEN")
    return kb


def _enqueue_ingestion(job_id: str, document_id: str) -> None:
    try:
        from app.tasks.agent_tasks import rag_ingest_document

        rag_ingest_document.delay(job_id=job_id, document_id=document_id)
    except Exception as exc:
        log_with_fields(
            logger,
            logging.ERROR,
            "rag_ingestion_enqueue_failed",
            job_id=job_id,
            document_id=document_id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG_QUEUE_UNAVAILABLE",
        ) from exc


def _document_out(document: Any) -> dict[str, Any]:
    return {
        "id": document.id,
        "knowledge_base_id": document.knowledge_base_id,
        "owner_user_id": document.owner_user_id,
        "title": document.title,
        "source_type": document.source_type,
        "source_uri": document.source_uri,
        "mime_type": document.mime_type,
        "status": document.status,
        "error_message": document.error_message,
        "meta": document.meta,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _status_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _assert_rag_admin(user: str, settings: Settings) -> None:
    if user in _rag_admin_user_ids(settings):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="RAG_ADMIN_FORBIDDEN",
    )


def _rag_admin_user_ids(settings: Settings) -> set[str]:
    return {
        item.strip()
        for item in (settings.rag_admin_user_ids or "").split(",")
        if item.strip()
    }


def _strict_status(reason: str) -> int:
    if reason in {"knowledge_base_not_found"}:
        return status.HTTP_404_NOT_FOUND
    if reason in {"knowledge_base_disabled"}:
        return status.HTTP_409_CONFLICT
    if reason in {"timeout", "error"}:
        return status.HTTP_503_SERVICE_UNAVAILABLE
    return status.HTTP_400_BAD_REQUEST
