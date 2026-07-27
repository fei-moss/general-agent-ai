"""Pending/stuck run reaper."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import argparse
import asyncio
import logging
import time
from typing import Any

from sqlalchemy import and_, or_, select

from app.api.runner_gateway import enqueue_run
from app.core.config import get_settings
from app.core.enums import (
    RAGDocumentStatus,
    RAGIngestionJobStatus,
    RunStatus,
    TaskStatus,
)
from app.core.events import AgentEvent, EventType
from app.core.logging import configure_logging, get_logger, log_with_fields
from app.core.metrics import Metrics
from app.core.models import AgentRun, RAGDocument, RAGIngestionJob, TaskState
from app.db.session import async_session_factory
from app.db.state_machine import is_terminal_run_status
from app.runtime.locks import RunLease

logger = get_logger(__name__)


@dataclass
class ReaperResult:
    inspected: int = 0
    requeued: int = 0
    failed: int = 0
    ignored: int = 0
    rag_requeued: int = 0
    rag_failed: int = 0


class PendingRunReaper:
    """Recover stale batch runs and orphan realtime RUNNING runs."""

    def __init__(
        self,
        *,
        store: Any | None = None,
        run_lease: RunLease | None = None,
        stale_after_s: int = 300,
        max_attempts: int = 3,
        metrics: Metrics | None = None,
    ) -> None:
        self._store = store or DbPendingRunStore(
            stale_after_s=stale_after_s,
            max_attempts=max_attempts,
        )
        self._run_lease = run_lease or RunLease()
        self._max_attempts = max_attempts
        self._metrics = metrics or Metrics()

    async def run_once(self, *, dry_run: bool = False) -> ReaperResult:
        started = time.perf_counter()
        result = ReaperResult()
        for run in await self._store.list_stale_runs():
            result.inspected += 1
            run_status = getattr(run, "run_status", getattr(run, "status", None))
            if _is_terminal_run_status(run_status):
                result.ignored += 1
                continue
            status = _status_value(getattr(run, "status", None))
            route_type = _route_type(run)
            if (
                status in {RunStatus.PENDING.value, RunStatus.RUNNING.value}
                and route_type == "realtime"
            ):
                if await self._run_lease.is_alive(run.id):
                    result.ignored += 1
                    continue
                if not dry_run:
                    await self._store.mark_failed(run, "orphan realtime run lease expired")
                result.failed += 1
                continue
            if status in {
                RunStatus.PENDING.value,
                TaskStatus.QUEUED.value,
                TaskStatus.RUNNING.value,
            }:
                attempt = int(getattr(run, "attempt", 0) or 0)
                if attempt >= self._max_attempts:
                    if not dry_run:
                        await self._store.mark_failed(run, "reaper attempt budget exhausted")
                    result.failed += 1
                    continue
                if not dry_run:
                    await self._store.reenqueue(run)
                result.requeued += 1
                continue
            result.ignored += 1
        list_rag_jobs = getattr(self._store, "list_stale_rag_jobs", None)
        if callable(list_rag_jobs):
            for job in await list_rag_jobs():
                if int(getattr(job, "dispatch_attempts", 0) or 0) >= self._max_attempts:
                    if not dry_run:
                        await self._store.mark_rag_failed(
                            job,
                            "RAG dispatch attempt budget exhausted",
                        )
                    result.rag_failed += 1
                    continue
                if not dry_run:
                    await self._store.reenqueue_rag(job)
                result.rag_requeued += 1
        self._observe_result(result, dry_run=dry_run, elapsed_s=time.perf_counter() - started)
        return result

    def _observe_result(
        self, result: ReaperResult, *, dry_run: bool, elapsed_s: float
    ) -> None:
        labels = {"dry_run": str(dry_run).lower()}
        self._metrics.inc_counter("reaper_runs_total", labels)
        self._metrics.inc_counter("reaper_inspected_total", labels, result.inspected)
        self._metrics.inc_counter("reaper_requeued_total", labels, result.requeued)
        self._metrics.inc_counter("reaper_failed_total", labels, result.failed)
        self._metrics.inc_counter(
            "reaper_rag_requeued_total", labels, result.rag_requeued
        )
        self._metrics.inc_counter("reaper_rag_failed_total", labels, result.rag_failed)
        self._metrics.observe_histogram("reaper_run_seconds", elapsed_s, labels)


def _status_value(status: Any) -> str:
    return status.value if hasattr(status, "value") else str(status)


def _is_terminal_run_status(status: Any) -> bool:
    try:
        return is_terminal_run_status(RunStatus(_status_value(status)))
    except ValueError:
        return False


def _route_type(run: Any) -> str:
    direct = getattr(run, "route_type", None)
    if direct:
        return str(direct)
    plan = getattr(run, "plan", None) or {}
    if isinstance(plan, dict):
        return str(plan.get("route_type") or "batch")
    return "batch"


@dataclass
class ReaperItem:
    id: str
    status: Any
    route_type: str
    attempt: int = 0
    payload: dict[str, Any] | None = None
    task_id: str | None = None
    run_status: Any | None = None
    trace_id: str = ""


@dataclass
class RAGReaperItem:
    id: str
    document_id: str
    dispatch_attempts: int = 0


class DbPendingRunStore:
    """DB-backed stale run/task store for PendingRunReaper."""

    def __init__(
        self,
        *,
        stale_after_s: int = 300,
        max_attempts: int = 3,
        event_bus: Any | None = None,
    ) -> None:
        self._stale_after_s = stale_after_s
        self._max_attempts = max_attempts
        self._event_bus = event_bus

    async def list_stale_runs(self) -> list[ReaperItem]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._stale_after_s)
        items: list[ReaperItem] = []
        async with async_session_factory() as session:
            task_stmt = (
                select(TaskState, AgentRun)
                .join(AgentRun, AgentRun.id == TaskState.agent_run_id)
                .where(TaskState.status.in_([TaskStatus.QUEUED, TaskStatus.RUNNING]))
                .where(AgentRun.status.in_([RunStatus.PENDING, RunStatus.RUNNING]))
                .where(TaskState.updated_at < cutoff)
            )
            task_result = await session.execute(task_stmt)
            for task, run in task_result.all():
                items.append(
                    ReaperItem(
                        id=run.id,
                        status=task.status,
                        route_type=_route_type(run),
                        attempt=task.attempt or 0,
                        payload=task.payload,
                        task_id=task.id,
                        run_status=run.status,
                        trace_id=run.trace_id,
                    )
                )

            run_stmt = select(AgentRun).where(
                or_(
                    and_(
                        AgentRun.status == RunStatus.RUNNING,
                        AgentRun.started_at.is_not(None),
                        AgentRun.started_at < cutoff,
                    ),
                    and_(
                        AgentRun.status == RunStatus.PENDING,
                        AgentRun.created_at < cutoff,
                    ),
                )
            )
            run_result = await session.execute(run_stmt)
            for run in run_result.scalars().all():
                if _route_type(run) == "realtime":
                    items.append(
                        ReaperItem(
                            id=run.id,
                            status=run.status,
                            route_type="realtime",
                            attempt=0,
                            run_status=run.status,
                            trace_id=run.trace_id,
                        )
                    )
        return items

    async def list_stale_rag_jobs(self) -> list[RAGReaperItem]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._stale_after_s)
        async with async_session_factory() as session:
            stmt = select(RAGIngestionJob).where(
                or_(
                    and_(
                        RAGIngestionJob.status == RAGIngestionJobStatus.PENDING,
                        RAGIngestionJob.last_dispatched_at.is_(None),
                        RAGIngestionJob.created_at < cutoff,
                    ),
                    and_(
                        RAGIngestionJob.status == RAGIngestionJobStatus.PENDING,
                        RAGIngestionJob.last_dispatched_at < cutoff,
                    ),
                    and_(
                        RAGIngestionJob.status == RAGIngestionJobStatus.RUNNING,
                        RAGIngestionJob.started_at.is_not(None),
                        RAGIngestionJob.started_at < cutoff,
                    ),
                ),
            )
            jobs = (await session.scalars(stmt)).all()
            return [
                RAGReaperItem(
                    id=job.id,
                    document_id=job.document_id,
                    dispatch_attempts=job.dispatch_attempts or 0,
                )
                for job in jobs
            ]

    async def reenqueue_rag(self, job: RAGReaperItem) -> None:
        from app.tasks.agent_tasks import rag_ingest_document

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=self._stale_after_s)
        async with async_session_factory() as session:
            db_job = await session.get(RAGIngestionJob, job.id, with_for_update=True)
            if db_job is None or db_job.status not in {
                RAGIngestionJobStatus.PENDING,
                RAGIngestionJobStatus.RUNNING,
            }:
                return
            if db_job.status == RAGIngestionJobStatus.PENDING:
                dispatched_at = db_job.last_dispatched_at
                created_at = getattr(db_job, "created_at", None)
                if dispatched_at is not None and dispatched_at >= cutoff:
                    return
                if dispatched_at is None and created_at is not None and created_at >= cutoff:
                    return
            elif db_job.started_at is None or db_job.started_at >= cutoff:
                return
            db_job.status = RAGIngestionJobStatus.PENDING
            db_job.dispatch_attempts = (db_job.dispatch_attempts or 0) + 1
            db_job.last_dispatched_at = now
            db_job.started_at = None
            db_job.error_message = None
            document = await session.get(RAGDocument, job.document_id)
            if document is not None and document.status not in {
                RAGDocumentStatus.EMBEDDED,
                RAGDocumentStatus.DELETED,
            }:
                document.status = RAGDocumentStatus.PENDING
                document.error_message = None
            await session.commit()
        rag_ingest_document.delay(job_id=job.id, document_id=job.document_id)

    async def mark_rag_failed(self, job: RAGReaperItem, reason: str) -> None:
        async with async_session_factory() as session:
            db_job = await session.get(RAGIngestionJob, job.id)
            if db_job is None or db_job.status not in {
                RAGIngestionJobStatus.PENDING,
                RAGIngestionJobStatus.RUNNING,
            }:
                return
            db_job.status = RAGIngestionJobStatus.FAILED
            db_job.error_message = reason
            db_job.finished_at = datetime.now(timezone.utc)
            document = await session.get(RAGDocument, job.document_id)
            if document is not None and document.status not in {
                RAGDocumentStatus.EMBEDDED,
                RAGDocumentStatus.DELETED,
            }:
                document.status = RAGDocumentStatus.FAILED
                document.error_message = reason
            await session.commit()

    async def reenqueue(self, run: ReaperItem) -> None:
        if not run.payload:
            await self.mark_failed(run, "missing task payload for requeue")
            return
        if run.task_id is not None:
            async with async_session_factory() as session:
                task = await session.get(TaskState, run.task_id)
                db_run = await session.get(AgentRun, run.id)
                if (
                    task is None
                    or db_run is None
                    or is_terminal_run_status(db_run.status)
                ):
                    return
                task.attempt = (task.attempt or 0) + 1
                task.status = TaskStatus.QUEUED
                task.updated_at = datetime.now(timezone.utc)
                await session.commit()
        enqueue_run(run.payload)

    async def mark_failed(self, run: ReaperItem, reason: str) -> None:
        trace_id = run.trace_id
        changed = False
        async with async_session_factory() as session:
            db_run = await session.get(AgentRun, run.id)
            if db_run is not None and not is_terminal_run_status(db_run.status):
                db_run.status = RunStatus.FAILED
                db_run.error = reason
                db_run.finished_at = datetime.now(timezone.utc)
                trace_id = db_run.trace_id
                changed = True
            if run.task_id is not None:
                task = await session.get(TaskState, run.task_id)
                if task is not None and changed:
                    task.status = TaskStatus.ERROR
                    task.result = {"error": reason}
                    task.updated_at = datetime.now(timezone.utc)
            await session.commit()
        if changed:
            await self._publish_terminal_failure(run.id, trace_id, reason)

    async def _publish_terminal_failure(
        self, run_id: str, trace_id: str, reason: str
    ) -> None:
        if self._event_bus is None:
            from app.bus.stream_bus import StreamBus

            self._event_bus = StreamBus()
        error_event = AgentEvent(
            agent_run_id=run_id,
            trace_id=trace_id,
            type=EventType.ERROR,
            seq=0,
            data={"stage": "reaper", "error": reason},
        )
        completed_event = AgentEvent(
            agent_run_id=run_id,
            trace_id=trace_id,
            type=EventType.RUN_COMPLETED,
            seq=1,
            data={"status": RunStatus.FAILED.value},
        )
        try:
            await self._event_bus.publish(run_id, error_event)
            await self._event_bus.publish(run_id, completed_event)
        except Exception as exc:  # noqa: BLE001 database terminal state remains authoritative
            log_with_fields(
                logger,
                logging.ERROR,
                "reaper_terminal_event_failed",
                agent_run_id=run_id,
                error=type(exc).__name__,
            )


async def run_reaper_loop(
    reaper: PendingRunReaper,
    *,
    interval_s: float,
    dry_run: bool = False,
    stop_after: int | None = None,
    enabled: bool = True,
    sleep: Any = asyncio.sleep,
) -> None:
    """Run the pending-run reaper on a fixed interval."""
    iteration = 0
    while True:
        iteration += 1
        if not enabled:
            if stop_after is not None and iteration >= stop_after:
                return
            await sleep(interval_s)
            continue
        try:
            result = await reaper.run_once(dry_run=dry_run)
            log_with_fields(
                logger,
                logging.INFO,
                "pending_run_reaper_completed",
                inspected=result.inspected,
                requeued=result.requeued,
                failed=result.failed,
                ignored=result.ignored,
                rag_requeued=result.rag_requeued,
                rag_failed=result.rag_failed,
                dry_run=dry_run,
            )
        except Exception as exc:  # noqa: BLE001 daemon must keep trying
            Metrics().inc_counter("reaper_errors_total")
            log_with_fields(
                logger,
                logging.ERROR,
                "pending_run_reaper_failed",
                error=type(exc).__name__,
            )
        if stop_after is not None and iteration >= stop_after:
            return
        await sleep(interval_s)


def _parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Run the pending AgentRun reaper.")
    parser.add_argument("--once", action="store_true", help="run one scan then exit")
    parser.add_argument("--dry-run", action="store_true", help="do not mutate runs")
    parser.add_argument(
        "--interval-s",
        type=float,
        default=settings.reaper_interval_s,
        help="seconds between scans",
    )
    parser.add_argument(
        "--stale-after-s",
        type=int,
        default=settings.reaper_stale_after_s,
        help="age threshold for stale work",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=settings.reaper_max_attempts,
        help="maximum requeue attempts before failing work",
    )
    return parser.parse_args()


async def _amain() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    args = _parse_args()
    reaper = PendingRunReaper(
        stale_after_s=args.stale_after_s,
        max_attempts=args.max_attempts,
    )
    if args.once:
        if settings.reaper_enabled:
            await reaper.run_once(dry_run=args.dry_run)
        return
    await run_reaper_loop(
        reaper,
        interval_s=max(1.0, args.interval_s),
        dry_run=args.dry_run,
        enabled=settings.reaper_enabled,
    )


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
