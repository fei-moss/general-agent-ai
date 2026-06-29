"""InMemoryEventBus 测试:publish/subscribe 与 seq 单调递增。"""

from __future__ import annotations

import asyncio

from app.bus.event_bus import InMemoryEventBus, channel_for
from app.core.events import AgentEvent, EventType


def _make_event(run_id: str, seq: int, type_: EventType) -> AgentEvent:
    return AgentEvent(
        agent_run_id=run_id,
        trace_id="trace-1",
        type=type_,
        seq=seq,
    )


async def test_subscriber_receives_published_event():
    # Arrange
    bus = InMemoryEventBus()
    channel = channel_for("run-1")
    agen = bus.subscribe(channel).__aiter__()
    # 先挂起一次 __anext__,驱动生成器注册队列,再发布
    pending = asyncio.ensure_future(agen.__anext__())
    await asyncio.sleep(0)

    # Act
    await bus.publish(channel, _make_event("run-1", 1, EventType.RUN_STARTED))
    received = await asyncio.wait_for(pending, timeout=1.0)

    # Assert
    assert received.type is EventType.RUN_STARTED
    assert received.seq == 1
    await agen.aclose()


async def test_subscriber_receives_events_in_publish_order():
    # Arrange
    bus = InMemoryEventBus()
    channel = channel_for("run-2")
    agen = bus.subscribe(channel).__aiter__()
    # 先挂起一次 __anext__ 注册队列
    first = asyncio.ensure_future(agen.__anext__())
    await asyncio.sleep(0)
    types = [
        EventType.RUN_STARTED,
        EventType.LLM_GENERATING,
        EventType.RUN_COMPLETED,
    ]

    # Act
    for i, t in enumerate(types, start=1):
        await bus.publish(channel, _make_event("run-2", i, t))
    got = [(await asyncio.wait_for(first, timeout=1.0)).type]
    for _ in types[1:]:
        got.append(
            (await asyncio.wait_for(agen.__anext__(), timeout=1.0)).type
        )

    # Assert
    assert got == types
    await agen.aclose()


def test_next_seq_is_monotonic_within_a_run():
    # Arrange
    bus = InMemoryEventBus()

    # Act
    seqs = [bus.next_seq("run-3") for _ in range(5)]

    # Assert
    assert seqs == [0, 1, 2, 3, 4]


def test_next_seq_is_independent_per_run():
    # Arrange
    bus = InMemoryEventBus()

    # Act
    a0 = bus.next_seq("run-a")
    b0 = bus.next_seq("run-b")
    a1 = bus.next_seq("run-a")

    # Assert
    assert (a0, a1) == (0, 1)
    assert b0 == 0


async def test_publish_to_channel_without_subscribers_is_noop():
    # Arrange
    bus = InMemoryEventBus()

    # Act / Assert (不应抛出)
    await bus.publish(
        channel_for("ghost"), _make_event("ghost", 1, EventType.ERROR)
    )


async def test_multiple_subscribers_each_receive_event():
    # Arrange
    bus = InMemoryEventBus()
    channel = channel_for("run-fanout")
    a = bus.subscribe(channel).__aiter__()
    b = bus.subscribe(channel).__aiter__()
    # 先各挂起一次 __anext__ 注册队列
    pa = asyncio.ensure_future(a.__anext__())
    pb = asyncio.ensure_future(b.__anext__())
    await asyncio.sleep(0)

    # Act
    await bus.publish(channel, _make_event("run-fanout", 1, EventType.TOKEN))
    ra = await asyncio.wait_for(pa, timeout=1.0)
    rb = await asyncio.wait_for(pb, timeout=1.0)

    # Assert
    assert ra.type is EventType.TOKEN
    assert rb.type is EventType.TOKEN
    await a.aclose()
    await b.aclose()


async def test_unsubscribe_removes_queue_on_close():
    # Arrange
    bus = InMemoryEventBus()
    channel = channel_for("run-cleanup")
    agen = bus.subscribe(channel).__aiter__()
    # 挂起一次 __anext__ 以注册队列
    pending = asyncio.ensure_future(agen.__anext__())
    await asyncio.sleep(0)
    assert len(bus._subscribers.get(channel, [])) == 1

    # Act
    pending.cancel()
    try:
        await pending
    except asyncio.CancelledError:
        pass
    await agen.aclose()

    # Assert
    assert bus._subscribers.get(channel, []) == []
