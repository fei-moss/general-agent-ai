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
