"""app/bus 包。

在包级再导出事件总线实现与工厂,供调用方(如 app.api.lifespan)按
``from app.bus import create_event_bus / RedisEventBus`` 的约定导入。
"""

from __future__ import annotations

from app.bus.event_bus import (
    InMemoryEventBus,
    RedisEventBus,
    channel_for,
    get_event_bus,
    set_event_bus,
)
from app.bus.stream_bus import StreamBus


def create_event_bus(redis_url: str | None = None, redis_client=None, metrics=None) -> StreamBus:
    """按 redis_url 构造 Redis StreamBus(lifespan 约定的工厂入口)。"""
    return StreamBus(redis_url, redis_client=redis_client, metrics=metrics)


__all__ = [
    "InMemoryEventBus",
    "RedisEventBus",
    "StreamBus",
    "channel_for",
    "create_event_bus",
    "get_event_bus",
    "set_event_bus",
]
