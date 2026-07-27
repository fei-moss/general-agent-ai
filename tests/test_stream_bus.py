from __future__ import annotations

import pytest

from app.core.events import AgentEvent, EventType
from tests.harness_fakes import FakeStreamBus, HarnessEvent, StreamGapError


async def _collect(async_iter):
    return [item async for item in async_iter]


async def test_stream_bus_xadd_and_xrange_replay():
    bus = FakeStreamBus()

    first = await bus.publish("run-1", HarnessEvent("run-1", "RUN_STARTED"))
    second = await bus.publish("run-1", HarnessEvent("run-1", "TOKEN", {"token": "hi"}))

    assert first.stream_id == "1-0"
    assert second.stream_id == "2-0"
    assert await _collect(bus.replay("run-1", "1-0")) == [second]


async def test_stream_bus_detects_retention_gap():
    bus = FakeStreamBus()
    bus.gap_before_id = "5-0"

    with pytest.raises(StreamGapError):
        await _collect(bus.replay("run-1", "1-0"))


def test_agent_event_to_sse_uses_stream_id_when_available():
    event = AgentEvent(
        agent_run_id="run-1",
        trace_id="trace-1",
        type=EventType.TOKEN,
        seq=7,
        stream_id="42-0",
        data={"token": "hello"},
    )

    assert event.to_sse()["id"] == "42-0"


async def test_redis_stream_bus_publish_and_replay_injects_stream_id():
    from app.bus.stream_bus import StreamBus
    from app.core.metrics import InMemoryMetrics

    class _FakeRedis:
        def __init__(self) -> None:
            self.entries: list[tuple[str, dict[str, str]]] = []
            self.expirations: list[tuple[str, int]] = []

        async def xadd(self, name, fields, maxlen=None, approximate=True):
            stream_id = f"{len(self.entries) + 1}-0"
            self.entries.append((stream_id, fields))
            return stream_id

        async def xrange(self, name, min="-", max="+", count=None):
            entries = self.entries
            if min.startswith("("):
                after = min[1:]
                entries = [
                    (stream_id, fields)
                    for stream_id, fields in entries
                    if stream_id > after
                ]
            if count is not None:
                entries = entries[:count]
            return entries

        async def expire(self, name, ttl):
            self.expirations.append((name, ttl))

    redis = _FakeRedis()
    metrics = InMemoryMetrics()
    bus = StreamBus(redis_client=redis, ttl_s=60, metrics=metrics)
    event = AgentEvent(
        agent_run_id="run-1",
        trace_id="trace-1",
        type=EventType.TOKEN,
        seq=1,
        data={"token": "hello"},
    )

    published = await bus.publish("run-1", event)
    replayed = await _collect(bus.replay("run-1", None))

    assert published.stream_id == "1-0"
    assert replayed[0].stream_id == "1-0"
    assert replayed[0].data == {"token": "hello"}
    assert redis.expirations == [("stream:run:run-1", 60)]
    assert metrics.counters["redis_stream_events_total"][0][1] == {}
    assert metrics.gauges["redis_stream_lag_events"][0][1] == {}


async def test_redis_stream_subscribe_does_not_lose_event_at_replay_handoff():
    from app.bus.stream_bus import StreamBus

    event = AgentEvent(
        agent_run_id="run-race",
        trace_id="trace-race",
        type=EventType.TOKEN,
        seq=1,
        data={"token": "arrived-between-replay-and-live"},
    )

    class _RaceRedis:
        async def xrange(self, name, min="-", max="+", count=None):
            return []

        async def xread(self, streams, count=1, block=None):
            assert streams == {"stream:run:run-race": "0-0"}
            return [
                (
                    "stream:run:run-race",
                    [("1-0", {"event": event.to_json()})],
                )
            ]

    bus = StreamBus(redis_client=_RaceRedis(), block_ms=1)
    subscription = bus.subscribe("run-race")

    received = await anext(subscription)
    await subscription.aclose()

    assert received.stream_id == "1-0"
    assert received.data["token"] == "arrived-between-replay-and-live"
