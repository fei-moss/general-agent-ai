"""Application services for lightweight RAG ingestion and query."""

from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Any

from app.core.config import Settings, get_settings
from app.core.enums import (
    KnowledgeBaseStatus,
    RAGDocumentStatus,
    RAGIngestionJobStatus,
)
from app.core.ids import _new_id
from app.core.schemas import (
    CitationOut,
    KnowledgeSearchResult,
    RAGQueryResponse,
)
from app.rag.chunker import chunk_text
from app.rag.embedder import get_embedder
from app.rag.parser import parse_text_document
from app.rag.vector_store import get_vector_store


class RAGQueryError(RuntimeError):
    """Raised only for strict RAG query callers."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class RAGQueryService:
    """Owner-scoped RAG query service with timeout/degraded behavior."""

    def __init__(
        self,
        *,
        knowledge_base_repo: Any | None = None,
        retrieval_log_repo: Any | None = None,
        embedder: Any | None = None,
        vector_store: Any | None = None,
        settings: Settings | None = None,
        metrics: Any | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._knowledge_base_repo = knowledge_base_repo or _ScopedKnowledgeBaseRepo()
        self._retrieval_log_repo = retrieval_log_repo or _ScopedRetrievalLogRepo()
        self._embedder = embedder or get_embedder(self._settings)
        self._vector_store = vector_store or get_vector_store(self._settings)
        self._metrics = metrics

    async def query(
        self,
        *,
        user_id: str,
        knowledge_base_id: str | None,
        query: str,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
        agent_run_id: str | None = None,
        conversation_id: str | None = None,
        strict: bool = False,
    ) -> RAGQueryResponse:
        started = time.perf_counter()
        k = self._bounded_top_k(top_k)
        if not knowledge_base_id:
            result = self._response([], True, "no_knowledge_base", started)
            if strict:
                raise RAGQueryError(result.reason or "no_knowledge_base")
            return result

        try:
            result = await asyncio.wait_for(
                self._query_inner(
                    user_id=user_id,
                    knowledge_base_id=knowledge_base_id,
                    query=query,
                    top_k=k,
                    filters=filters or {},
                    started=started,
                ),
                timeout=max(self._settings.rag_query_timeout_ms, 1) / 1000,
            )
        except asyncio.TimeoutError:
            result = self._response([], True, "timeout", started)
        except Exception as exc:  # noqa: BLE001 - Agent path must degrade.
            result = self._response([], True, _sanitize_reason(str(exc)), started)

        result = await self._write_log(
            result,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            query=query,
            top_k=k,
            agent_run_id=agent_run_id,
            conversation_id=conversation_id,
        )
        self._observe(result)
        if result.degraded and strict:
            raise RAGQueryError(result.reason or "error")
        return result

    async def _query_inner(
        self,
        *,
        user_id: str,
        knowledge_base_id: str,
        query: str,
        top_k: int,
        filters: dict[str, Any],
        started: float,
    ) -> RAGQueryResponse:
        kb = await self._knowledge_base_repo.get_for_user(knowledge_base_id, user_id)
        if kb is None:
            return self._response([], True, "knowledge_base_not_found", started)
        status = getattr(kb, "status", "")
        status_value = status.value if hasattr(status, "value") else str(status)
        if status_value != KnowledgeBaseStatus.ACTIVE.value:
            return self._response([], True, "knowledge_base_disabled", started)

        vectors = await self._embedder.embed([query])
        query_vec = vectors[0] if vectors else []
        if len(query_vec) != self._settings.embedding_dim:
            return self._response([], True, "embedding_dimension_mismatch", started)

        hits = await _search_vector_store(
            self._vector_store,
            query_vec,
            top_k,
            owner_user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            index_version=self._settings.rag_index_version,
            filters=filters,
            score_threshold=self._settings.rag_score_threshold,
        )
        chunks = self._map_hits(hits, knowledge_base_id)
        return self._response(chunks, False, None, started)

    def _map_hits(
        self, hits: list[tuple[dict[str, Any], float]], knowledge_base_id: str
    ) -> list[KnowledgeSearchResult]:
        output: list[KnowledgeSearchResult] = []
        used_chars = 0
        for doc, score in hits:
            if score < self._settings.rag_score_threshold:
                continue
            content = str(doc.get("content") or doc.get("text") or "")
            if not content:
                continue
            if used_chars + len(content) > self._settings.rag_max_context_chars:
                remaining = max(self._settings.rag_max_context_chars - used_chars, 0)
                if remaining <= 0:
                    break
                content = content[:remaining]
            used_chars += len(content)
            metadata = dict(doc.get("metadata") or doc.get("meta") or {})
            citation_data = dict(doc.get("citation") or {})
            chunk_index = int(
                citation_data.get("chunk_index", metadata.get("chunk", 0))
            )
            output.append(
                KnowledgeSearchResult(
                    chunk_id=str(doc.get("chunk_id") or doc.get("id") or ""),
                    document_id=str(
                        doc.get("document_id") or metadata.get("doc_id") or ""
                    ),
                    knowledge_base_id=str(
                        doc.get("knowledge_base_id") or knowledge_base_id
                    ),
                    title=doc.get("title"),
                    content=content,
                    score=float(score),
                    citation=CitationOut(
                        source_uri=citation_data.get(
                            "source_uri", metadata.get("source_uri")
                        ),
                        page=citation_data.get("page", metadata.get("page")),
                        section=citation_data.get(
                            "section", metadata.get("section")
                        ),
                        chunk_index=chunk_index,
                    ),
                    metadata=metadata,
                )
            )
        return output

    def _bounded_top_k(self, top_k: int | None) -> int:
        requested = top_k or self._settings.rag_default_top_k
        return max(1, min(int(requested), self._settings.rag_max_top_k))

    @staticmethod
    def _response(
        chunks: list[KnowledgeSearchResult],
        degraded: bool,
        reason: str | None,
        started: float,
    ) -> RAGQueryResponse:
        return RAGQueryResponse(
            chunks=chunks,
            degraded=degraded,
            reason=reason,
            latency_ms=max(0, int((time.perf_counter() - started) * 1000)),
            query_id=None,
        )

    async def _write_log(
        self,
        result: RAGQueryResponse,
        *,
        user_id: str,
        knowledge_base_id: str,
        query: str,
        top_k: int,
        agent_run_id: str | None,
        conversation_id: str | None,
    ) -> RAGQueryResponse:
        try:
            log = await self._retrieval_log_repo.create(
                agent_run_id=agent_run_id,
                conversation_id=conversation_id,
                user_id=user_id,
                knowledge_base_id=knowledge_base_id,
                query_hash=_content_hash(query),
                query_preview=_preview(query),
                top_k=top_k,
                matched_chunk_ids=[chunk.chunk_id for chunk in result.chunks],
                scores=[chunk.score for chunk in result.chunks],
                latency_ms=result.latency_ms,
                degraded=result.degraded,
                reason=result.reason,
            )
            return result.model_copy(update={"query_id": getattr(log, "id", None)})
        except Exception:
            return result

    def _observe(self, result: RAGQueryResponse) -> None:
        if self._metrics is None:
            return
        labels = {
            "degraded": str(result.degraded).lower(),
            "reason": result.reason or "none",
        }
        self._metrics.observe_histogram(
            "rag_query_seconds", result.latency_ms / 1000, labels
        )
        if result.degraded:
            self._metrics.inc_counter("rag_query_degraded_total", labels)
        if not result.chunks:
            self._metrics.inc_counter("rag_query_empty_result_total")


class RAGIngestionService:
    """Worker-side text ingestion service."""

    def __init__(
        self,
        *,
        document_repo: Any | None = None,
        job_repo: Any | None = None,
        vector_store: Any | None = None,
        embedder: Any | None = None,
        settings: Settings | None = None,
        metrics: Any | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._document_repo = document_repo or _ScopedDocumentRepo()
        self._job_repo = job_repo or _ScopedIngestionJobRepo()
        self._vector_store = vector_store or get_vector_store(self._settings)
        self._embedder = embedder or get_embedder(self._settings)
        self._metrics = metrics

    async def ingest_document(self, *, job_id: str, document_id: str) -> int:
        started = time.perf_counter()
        try:
            await self._job_repo.update_status(job_id, RAGIngestionJobStatus.RUNNING)
            await self._document_repo.update_status(
                document_id, RAGDocumentStatus.PARSING
            )
            document = await self._document_repo.get(document_id)
            if document is None:
                raise ValueError(f"document not found: {document_id}")
            parsed = parse_text_document(
                getattr(document, "raw_content", ""),
                mime_type=getattr(document, "mime_type", None),
                metadata=getattr(document, "meta", {}) or {},
            )
            chunks = chunk_text(
                parsed.text,
                chunk_size=self._settings.rag_chunk_size,
                overlap=self._settings.rag_chunk_overlap,
            )
            await self._document_repo.update_status(
                document_id, RAGDocumentStatus.EMBEDDING
            )
            vectors = await self._embedder.embed([chunk.text for chunk in chunks])
            records = []
            for chunk, vector in zip(chunks, vectors):
                if len(vector) != self._settings.embedding_dim:
                    raise ValueError("embedding_dimension_mismatch")
                records.append(
                    {
                        "id": _new_id("chunk_"),
                        "chunk_id": None,
                        "document_id": document_id,
                        "knowledge_base_id": getattr(document, "knowledge_base_id"),
                        "owner_user_id": getattr(document, "owner_user_id"),
                        "chunk_index": chunk.index,
                        "text": chunk.text,
                        "content": chunk.text,
                        "content_hash": _content_hash(chunk.text),
                        "token_count": len(chunk.text),
                        "metadata": {
                            **parsed.metadata,
                            "doc_id": document_id,
                            "chunk": chunk.index,
                            "source_uri": getattr(document, "source_uri", None),
                        },
                        "citation": {
                            "source_uri": getattr(document, "source_uri", None),
                            "page": None,
                            "section": parsed.metadata.get("section"),
                            "chunk_index": chunk.index,
                        },
                        "vector": vector,
                        "embedding": vector,
                        "embedding_provider": self._settings.embedding_provider,
                        "embedding_model": self._settings.embedding_model,
                        "embedding_dim": self._settings.embedding_dim,
                        "index_version": self._settings.rag_index_version,
                    }
                )
            await self._vector_store.add(records)
            await self._document_repo.update_status(
                document_id, RAGDocumentStatus.EMBEDDED
            )
            await self._job_repo.update_status(job_id, RAGIngestionJobStatus.SUCCEEDED)
            self._observe_ingestion("SUCCEEDED", started)
            return len(records)
        except Exception as exc:
            reason = _sanitize_reason(str(exc))
            await self._document_repo.update_status(
                document_id, RAGDocumentStatus.FAILED, error_message=reason
            )
            await self._job_repo.update_status(
                job_id, RAGIngestionJobStatus.FAILED, error_message=reason
            )
            self._observe_ingestion("FAILED", started, reason=reason)
            raise

    def _observe_ingestion(
        self, status: str, started: float, *, reason: str | None = None
    ) -> None:
        if self._metrics is None:
            return
        self._metrics.inc_counter("rag_ingestion_jobs_total", {"status": status})
        self._metrics.observe_histogram(
            "rag_ingestion_duration_seconds", time.perf_counter() - started
        )
        if reason:
            self._metrics.inc_counter(
                "rag_ingestion_failures_total", {"reason": reason}
            )


async def _search_vector_store(
    store: Any,
    query_vec: list[float],
    top_k: int,
    **kwargs: Any,
) -> list[tuple[dict[str, Any], float]]:
    try:
        return await store.search(query_vec, top_k, **kwargs)
    except TypeError:
        return await store.search(query_vec, top_k)


def build_query_service(settings: Settings | None = None, **overrides: Any) -> RAGQueryService:
    return RAGQueryService(settings=settings, **overrides)


def build_ingestion_service(
    settings: Settings | None = None, **overrides: Any
) -> RAGIngestionService:
    return RAGIngestionService(settings=settings, **overrides)


class _ScopedKnowledgeBaseRepo:
    async def get_for_user(self, knowledge_base_id: str, owner_user_id: str) -> Any:
        from app.db.repositories import KnowledgeBaseRepository
        from app.db.session import async_session_factory

        async with async_session_factory() as session:
            return await KnowledgeBaseRepository(session).get_for_user(
                knowledge_base_id, owner_user_id
            )


class _ScopedRetrievalLogRepo:
    async def create(self, **kwargs: Any) -> Any:
        from app.db.repositories import RAGRetrievalLogRepository
        from app.db.session import async_session_factory

        async with async_session_factory() as session:
            return await RAGRetrievalLogRepository(session).create(**kwargs)


class _ScopedDocumentRepo:
    async def get(self, document_id: str) -> Any:
        from app.db.repositories import RAGDocumentRepository
        from app.db.session import async_session_factory

        async with async_session_factory() as session:
            return await RAGDocumentRepository(session).get(document_id)

    async def update_status(
        self,
        document_id: str,
        status: RAGDocumentStatus,
        *,
        error_message: str | None = None,
    ) -> Any:
        from app.db.repositories import RAGDocumentRepository
        from app.db.session import async_session_factory

        async with async_session_factory() as session:
            return await RAGDocumentRepository(session).update_status(
                document_id, status, error_message=error_message
            )


class _ScopedIngestionJobRepo:
    async def update_status(
        self,
        job_id: str,
        status: RAGIngestionJobStatus,
        *,
        error_message: str | None = None,
    ) -> Any:
        from app.db.repositories import RAGIngestionJobRepository
        from app.db.session import async_session_factory

        async with async_session_factory() as session:
            return await RAGIngestionJobRepository(session).update_status(
                job_id, status, error_message=error_message
            )


def _content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _preview(text: str, max_len: int = 256) -> str:
    compact = " ".join((text or "").split())
    return compact[:max_len]


def _sanitize_reason(reason: str) -> str:
    if not reason:
        return "error"
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in reason)
    return safe[:64] or "error"
