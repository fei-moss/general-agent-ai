"""Pending/stuck run reaper."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.api.runner_gateway import enqueue_run
from app.core.enums import RunStatus, TaskStatus
from app.core.models import AgentRun, TaskState
from app.db.session import async_session_factory
from app.runtime.locks import RunLease


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
        max_attempts: int = 3,
    ) -> None:
        self._store = store or DbPendingRunStore(max_attempts=max_attempts)
        self._run_lease = run_lease or RunLease()
        self._max_attempts = max_attempts

    async def run_once(self, *, dry_run: bool = False) -> ReaperResult:
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
        return result


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
