from __future__ import annotations

from dataclasses import dataclass

from app.core.enums import RunStatus
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
