"""Pending/stuck run reaper."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import argparse
import asyncio
import logging
import time
from typing import Any

from sqlalchemy import select

from app.api.runner_gateway import enqueue_run
from app.core.config import get_settings
from app.core.enums import RunStatus, TaskStatus
from app.core.logging import configure_logging, get_logger, log_with_fields
from app.core.metrics import Metrics
from app.core.models import AgentRun, TaskState
from app.db.session import async_session_factory
from app.runtime.locks import RunLease

logger = get_logger(__name__)


@dataclass
class ReaperResult:
    inspected: int = 0
    requeued: int = 0
    failed: int = 0
    ignored: int = 0


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
            status = _status_value(getattr(run, "status", None))
            route_type = _route_type(run)
            if status == RunStatus.RUNNING.value and route_type == "realtime":
                if await self._run_lease.is_alive(run.id):
                    result.ignored += 1
                    continue
                if not dry_run:
                    await self._store.mark_failed(run, "orphan realtime run lease expired")
                result.failed += 1
                continue
            if status in {RunStatus.PENDING.value, "QUEUED"}:
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
        self._metrics.observe_histogram("reaper_run_seconds", elapsed_s, labels)


def _status_value(status: Any) -> str:
    return status.value if hasattr(status, "value") else str(status)


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


class DbPendingRunStore:
    """DB-backed stale run/task store for PendingRunReaper."""

    def __init__(self, *, stale_after_s: int = 300, max_attempts: int = 3) -> None:
        self._stale_after_s = stale_after_s
        self._max_attempts = max_attempts

    async def list_stale_runs(self) -> list[ReaperItem]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._stale_after_s)
        items: list[ReaperItem] = []
        async with async_session_factory() as session:
            task_stmt = (
                select(TaskState, AgentRun)
                .join(AgentRun, AgentRun.id == TaskState.agent_run_id)
                .where(TaskState.status.in_([TaskStatus.QUEUED, TaskStatus.RUNNING]))
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
                    )
                )

            run_stmt = select(AgentRun).where(
                AgentRun.status == RunStatus.RUNNING,
                AgentRun.started_at.is_not(None),
                AgentRun.started_at < cutoff,
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
                        )
                    )
        return items

    async def reenqueue(self, run: ReaperItem) -> None:
        if not run.payload:
            await self.mark_failed(run, "missing task payload for requeue")
            return
        enqueue_run(run.payload)
        if run.task_id is None:
            return
        async with async_session_factory() as session:
            task = await session.get(TaskState, run.task_id)
            if task is not None:
                task.attempt = (task.attempt or 0) + 1
                task.status = TaskStatus.QUEUED
                task.updated_at = datetime.now(timezone.utc)
                await session.commit()

    async def mark_failed(self, run: ReaperItem, reason: str) -> None:
        async with async_session_factory() as session:
            db_run = await session.get(AgentRun, run.id)
            if db_run is not None:
                db_run.status = RunStatus.FAILED
                db_run.error = reason
                db_run.finished_at = datetime.now(timezone.utc)
            if run.task_id is not None:
                task = await session.get(TaskState, run.task_id)
                if task is not None:
                    task.status = TaskStatus.ERROR
                    task.result = {"error": reason}
                    task.updated_at = datetime.now(timezone.utc)
            await session.commit()


async def run_reaper_loop(
    reaper: PendingRunReaper,
    *,
    interval_s: float,
    dry_run: bool = False,
    stop_after: int | None = None,
    sleep: Any = asyncio.sleep,
) -> None:
    """Run the pending-run reaper on a fixed interval."""
    iteration = 0
    while True:
        iteration += 1
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
        await reaper.run_once(dry_run=args.dry_run)
        return
    await run_reaper_loop(
        reaper,
        interval_s=max(1.0, args.interval_s),
        dry_run=args.dry_run,
    )


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
