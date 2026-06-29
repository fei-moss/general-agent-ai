"""Reusable test fakes for the high-performance chat runtime harness."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


class StreamGapError(RuntimeError):
    """Raised when a replay cursor is older than retained stream entries."""


@dataclass
class HarnessEvent:
    agent_run_id: str
    type: str
    data: dict[str, Any] = field(default_factory=dict)
    seq: int = 0
    trace_id: str = "trace-test"
    stream_id: str | None = None


class FakeStreamBus:
    """Redis Stream-like event bus used by tests before production StreamBus exists."""

    def __init__(self) -> None:
        self._events: dict[str, list[tuple[str, Any]]] = defaultdict(list)
        self._subscribers: dict[str, list[asyncio.Queue[Any]]] = defaultdict(list)
        self.gap_before_id: str | None = None

    async def publish(self, run_id: str, event: Any) -> Any:
        stream_id = f"{len(self._events[run_id]) + 1}-0"
        event_with_id = self._inject_stream_id(event, stream_id)
        self._events[run_id].append((stream_id, event_with_id))
        for queue in list(self._subscribers.get(run_id, [])):
            await queue.put(event_with_id)
        return event_with_id

    async def replay(
        self, run_id: str, after_id: str | None
    ) -> AsyncIterator[Any]:
        if self.gap_before_id and after_id and self._compare(after_id, self.gap_before_id) < 0:
            raise StreamGapError(f"cursor {after_id} is outside retention")
        for stream_id, event in self._events.get(run_id, []):
            if after_id is None or self._compare(stream_id, after_id) > 0:
                yield self._inject_stream_id(event, stream_id)

    async def subscribe(
        self, run_id: str, after_id: str | None = None
    ) -> AsyncIterator[Any]:
        async for event in self.replay(run_id, after_id):
            yield event

        queue: asyncio.Queue[Any] = asyncio.Queue()
        self._subscribers[run_id].append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers[run_id].remove(queue)

    @staticmethod
    def _compare(left: str, right: str) -> int:
        left_ms, left_seq = (int(part) for part in left.split("-", 1))
        right_ms, right_seq = (int(part) for part in right.split("-", 1))
        return (left_ms > right_ms) - (left_ms < right_ms) or (
            (left_seq > right_seq) - (left_seq < right_seq)
        )

    @staticmethod
    def _inject_stream_id(event: Any, stream_id: str) -> Any:
        try:
            setattr(event, "stream_id", stream_id)
            return event
        except Exception:
            pass
        if hasattr(event, "model_copy"):
            copied = event.model_copy()
            object.__setattr__(copied, "stream_id", stream_id)
            return copied
        raise TypeError("event does not support stream_id injection")


class FakeClock:
    def __init__(self, initial: float = 0.0) -> None:
        self._now = initial
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self._now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self._now += seconds

    def advance(self, seconds: float) -> None:
        self._now += seconds


class FakeStreamingModel:
    def __init__(
        self,
        tokens: list[str],
        *,
        delay_s: float = 0.0,
        clock: FakeClock | None = None,
    ) -> None:
        self.tokens = tokens
        self.delay_s = delay_s
        self.clock = clock

    async def stream(self) -> AsyncIterator[str]:
        for index, token in enumerate(self.tokens):
            if index > 0 and self.delay_s:
                if self.clock is not None:
                    await self.clock.sleep(self.delay_s)
                else:
                    await asyncio.sleep(self.delay_s)
            yield token


class FakeDbSessionTracker:
    def __init__(self) -> None:
        self.active_connections = 0
        self.active_during_streaming = 0
        self.streaming = False

    @asynccontextmanager
    async def checkout(self) -> AsyncIterator[None]:
        self.active_connections += 1
        if self.streaming:
            self.active_during_streaming += 1
        try:
            yield
        finally:
            self.active_connections -= 1

    def start_streaming(self) -> None:
        self.streaming = True
        if self.active_connections:
            self.active_during_streaming += self.active_connections

    def stop_streaming(self) -> None:
        self.streaming = False


class FakeLockLease:
    def __init__(self, key: str) -> None:
        self.key = key
        self.renew_count = 0
        self.released = False
        self.fail_renew = False

    async def renew(self) -> None:
        if self.fail_renew:
            raise RuntimeError("renew failed")
        self.renew_count += 1

    async def release(self) -> None:
        self.released = True


class FakeConversationLock:
    def __init__(self, *, busy: bool = False) -> None:
        self.busy = busy
        self.acquired: list[tuple[str, str, int]] = []

    async def acquire(
        self, conversation_id: str, owner: str, ttl_s: int
    ) -> FakeLockLease | None:
        if self.busy:
            return None
        self.acquired.append((conversation_id, owner, ttl_s))
        return FakeLockLease(conversation_id)


class FakeRunLease:
    def __init__(self, clock: FakeClock | None = None) -> None:
        self.clock = clock or FakeClock()
        self._leases: dict[str, tuple[str, float, int]] = {}
        self.released: set[str] = set()

    async def start(self, run_id: str, runner_id: str, ttl_s: int) -> None:
        self._leases[run_id] = (runner_id, self.clock.now() + ttl_s, ttl_s)

    async def renew(self, run_id: str) -> None:
        runner_id, _, ttl_s = self._leases[run_id]
        self._leases[run_id] = (runner_id, self.clock.now() + ttl_s, ttl_s)

    async def release(self, run_id: str) -> None:
        self.released.add(run_id)
        self._leases.pop(run_id, None)

    async def is_alive(self, run_id: str) -> bool:
        lease = self._leases.get(run_id)
        if lease is None:
            return False
        _, expires_at, _ = lease
        return self.clock.now() < expires_at


@dataclass
class FakeIdempotencyRecord:
    user_id: str
    key: str
    request_hash: str
    run_id: str
    response: dict[str, Any]


class FakeIdempotencyStore:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], FakeIdempotencyRecord] = {}

    async def get(self, user_id: str, key: str) -> FakeIdempotencyRecord | None:
        return self._records.get((user_id, key))

    async def create(
        self,
        user_id: str,
        key: str,
        request_hash: str,
        run_id: str,
        response: dict[str, Any],
    ) -> FakeIdempotencyRecord:
        record = FakeIdempotencyRecord(
            user_id=user_id,
            key=key,
            request_hash=request_hash,
            run_id=run_id,
            response=response,
        )
        self._records[(user_id, key)] = record
        return record
