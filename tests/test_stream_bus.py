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

    class _FakeRedis:
        def __init__(self) -> None:
            self.entries: list[tuple[str, dict[str, str]]] = []

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

    bus = StreamBus(redis_client=_FakeRedis())
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
