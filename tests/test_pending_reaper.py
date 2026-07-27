from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.enums import RunStatus, TaskStatus
from tests.harness_fakes import FakeClock, FakeRunLease


async def test_pending_reaper_can_distinguish_live_and_expired_run_lease():
    clock = FakeClock()
    lease = FakeRunLease(clock)

    await lease.start("run-1", "runner-1", ttl_s=10)
    assert await lease.is_alive("run-1") is True

    clock.advance(11)
    assert await lease.is_alive("run-1") is False


async def test_pending_reaper_requeues_queued_and_fails_orphan_running_run():
    from app.tasks.reaper import PendingRunReaper

    @dataclass
    class _Run:
        id: str
        status: RunStatus
        route_type: str
        attempt: int = 0

    class _Store:
        def __init__(self) -> None:
            self.runs = [
                _Run("run-queued", RunStatus.PENDING, "batch", 0),
                _Run("run-orphan", RunStatus.RUNNING, "realtime", 0),
                _Run("run-live", RunStatus.RUNNING, "realtime", 0),
            ]
            self.requeued = []
            self.failed = []

        async def list_stale_runs(self):
            return self.runs

        async def reenqueue(self, run):
            self.requeued.append(run.id)

        async def mark_failed(self, run, reason):
            self.failed.append((run.id, reason))

    store = _Store()
    lease = FakeRunLease()
    await lease.start("run-live", "runner-1", ttl_s=30)

    result = await PendingRunReaper(store=store, run_lease=lease).run_once()

    assert result.requeued == 1
    assert result.failed == 1
    assert store.requeued == ["run-queued"]
    assert store.failed[0][0] == "run-orphan"


async def test_pending_reaper_dry_run_does_not_mutate_store():
    from app.tasks.reaper import PendingRunReaper

    @dataclass
    class _Run:
        id: str
        status: RunStatus
        route_type: str
        attempt: int = 0

    class _Store:
        def __init__(self) -> None:
            self.runs = [_Run("run-queued", RunStatus.PENDING, "batch", 0)]
            self.requeued = []
            self.failed = []

        async def list_stale_runs(self):
            return self.runs

        async def reenqueue(self, run):
            self.requeued.append(run.id)

        async def mark_failed(self, run, reason):
            self.failed.append((run.id, reason))

    store = _Store()

    result = await PendingRunReaper(store=store).run_once(dry_run=True)

    assert result.requeued == 1
    assert store.requeued == []
    assert store.failed == []


async def test_pending_reaper_never_requeues_task_for_terminal_run():
    from app.tasks.reaper import PendingRunReaper

    @dataclass
    class _Run:
        id: str
        status: TaskStatus
        run_status: RunStatus
        route_type: str = "batch"
        attempt: int = 0

    class _Store:
        def __init__(self) -> None:
            self.requeued: list[str] = []
            self.failed: list[str] = []

        async def list_stale_runs(self):
            return [
                _Run("run-succeeded", TaskStatus.QUEUED, RunStatus.SUCCEEDED),
                _Run("run-failed", TaskStatus.RUNNING, RunStatus.FAILED),
            ]

        async def reenqueue(self, run):
            self.requeued.append(run.id)

        async def mark_failed(self, run, reason):
            self.failed.append(run.id)

    store = _Store()

    result = await PendingRunReaper(store=store).run_once()

    assert result.ignored == 2
    assert result.requeued == 0
    assert result.failed == 0
    assert store.requeued == []
    assert store.failed == []


async def test_reaper_loop_continues_after_iteration_error():
    from app.tasks.reaper import run_reaper_loop

    class _Reaper:
        def __init__(self) -> None:
            self.calls = 0

        async def run_once(self, *, dry_run=False):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("transient")
            from app.tasks.reaper import ReaperResult

            return ReaperResult(inspected=1)

    sleeps: list[float] = []

    async def _sleep(seconds: float) -> None:
        sleeps.append(seconds)

    reaper = _Reaper()

    await run_reaper_loop(reaper, interval_s=0.5, stop_after=2, sleep=_sleep)

    assert reaper.calls == 2
    assert sleeps == [0.5]


async def test_pending_reaper_recovers_stale_rag_dispatch():
    from app.tasks.reaper import PendingRunReaper

    @dataclass
    class _Job:
        id: str
        document_id: str
        dispatch_attempts: int = 0

    class _Store:
        def __init__(self) -> None:
            self.requeued: list[str] = []

        async def list_stale_runs(self):
            return []

        async def list_stale_rag_jobs(self):
            return [_Job("job-1", "doc-1")]

        async def reenqueue_rag(self, job):
            self.requeued.append(job.id)

        async def mark_rag_failed(self, job, reason):
            raise AssertionError("fresh dispatch must be retried")

    store = _Store()

    result = await PendingRunReaper(store=store).run_once()

    assert result.rag_requeued == 1
    assert store.requeued == ["job-1"]


async def test_db_reaper_scans_stale_running_rag_jobs(monkeypatch):
    from app.core.enums import RAGIngestionJobStatus
    from app.tasks import reaper

    statements = []

    class _Scalars:
        def all(self):
            return []

    class _Session:
        async def scalars(self, statement):
            statements.append(statement)
            return _Scalars()

    @asynccontextmanager
    async def _session_factory():
        yield _Session()

    monkeypatch.setattr(reaper, "async_session_factory", _session_factory)

    await reaper.DbPendingRunStore(stale_after_s=60).list_stale_rag_jobs()

    params = statements[0].compile().params.values()
    statuses = {
        value.value if hasattr(value, "value") else value
        for value in params
    }
    assert RAGIngestionJobStatus.PENDING.value in statuses
    assert RAGIngestionJobStatus.RUNNING.value in statuses


async def test_db_reaper_recovers_running_rag_job_before_redispatch(monkeypatch):
    from app.core.enums import RAGIngestionJobStatus
    from app.tasks import agent_tasks, reaper

    job = type(
        "Job",
        (),
        {
            "id": "job-running",
            "document_id": "doc-running",
            "status": RAGIngestionJobStatus.RUNNING,
            "dispatch_attempts": 1,
            "last_dispatched_at": None,
            "started_at": datetime(2000, 1, 1, tzinfo=timezone.utc),
            "error_message": "worker lost",
        },
    )()
    document = type(
        "Document",
        (),
        {"status": "EMBEDDING", "error_message": "worker lost"},
    )()
    commits = 0
    dispatched: list[tuple[str, str]] = []

    class _Session:
        async def get(self, model, entity_id, **kwargs):
            return job if entity_id == job.id else document

        async def commit(self):
            nonlocal commits
            commits += 1

    @asynccontextmanager
    async def _session_factory():
        yield _Session()

    monkeypatch.setattr(reaper, "async_session_factory", _session_factory)
    monkeypatch.setattr(
        agent_tasks.rag_ingest_document,
        "delay",
        lambda *, job_id, document_id: dispatched.append((job_id, document_id)),
    )

    await reaper.DbPendingRunStore(stale_after_s=60).reenqueue_rag(
        reaper.RAGReaperItem(
            id=job.id,
            document_id=job.document_id,
            dispatch_attempts=job.dispatch_attempts,
        )
    )

    assert job.status == RAGIngestionJobStatus.PENDING
    assert job.dispatch_attempts == 2
    assert document.status.value == "PENDING"
    assert commits == 1
    assert dispatched == [(job.id, job.document_id)]
