from __future__ import annotations

import pytest
from fastapi import HTTPException

from tests.harness_fakes import FakeStreamBus, HarnessEvent


async def test_stream_replay_starts_after_last_event_id():
    bus = FakeStreamBus()
    await bus.publish("run-1", HarnessEvent("run-1", "RUN_STARTED"))
    missed = await bus.publish("run-1", HarnessEvent("run-1", "TOKEN", {"token": "A"}))
    await bus.publish("run-1", HarnessEvent("run-1", "TOKEN", {"token": "B"}))

    replayed = [event async for event in bus.replay("run-1", missed.stream_id)]

    assert [event.data["token"] for event in replayed] == ["B"]


async def test_stream_router_iter_events_uses_last_event_id_cursor():
    from app.api.routers.stream import _iter_events

    bus = FakeStreamBus()
    await bus.publish("run-1", HarnessEvent("run-1", "TOKEN", {"token": "A"}))
    cursor = (
        await bus.publish("run-1", HarnessEvent("run-1", "TOKEN", {"token": "B"}))
    ).stream_id
    await bus.publish("run-1", HarnessEvent("run-1", "RUN_COMPLETED", {"status": "SUCCEEDED"}))

    replayed = [event async for event in _iter_events(bus, "run-1", cursor)]

    assert [event.type for event in replayed] == ["RUN_COMPLETED"]


async def test_stream_router_converts_retention_gap_to_stable_error():
    from app.api.routers.stream import _iter_events
    from app.core.events import EventType
    from app.core.metrics import reset_default_metrics_registry

    reset_default_metrics_registry()
    bus = FakeStreamBus()
    bus.gap_before_id = "5-0"

    replayed = [event async for event in _iter_events(bus, "run-1", "1-0")]

    assert len(replayed) == 1
    assert replayed[0].type is EventType.ERROR
    assert replayed[0].data["error"] == "STREAM_GAP"
    assert replayed[0].data["last_event_id"] == "1-0"


async def test_stream_owner_mismatch_raises_403():
    from app.api.routers.stream import _assert_run_owner

    class _Run:
        conversation_id = "conv-1"

    class _Conversation:
        user_id = "owner-1"

    class _Repos:
        async def get_run(self, run_id):
            return _Run()

        async def get_conversation(self, conversation_id):
            return _Conversation()

    with pytest.raises(HTTPException) as exc:
        await _assert_run_owner("run-1", "other-user", _Repos())

    assert exc.value.status_code == 403
