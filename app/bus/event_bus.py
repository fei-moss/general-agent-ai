"""事件总线实现。

提供两种 EventBus(见 app.core.interfaces.EventBus 契约)实现:

- RedisEventBus:基于 redis.asyncio 的 Pub/Sub,频道 ``run:{agent_run_id}``,
  publish 写入 AgentEvent 的 JSON,subscribe 异步迭代产出 AgentEvent;
  含进程内 seq 单调递增分配与订阅侧断线重连。
- InMemoryEventBus:基于 asyncio.Queue 的进程内实现,用于测试与单进程 demo。

工厂 ``get_event_bus()`` 按配置返回单例。
"""

from __future__ import annotations

import asyncio
import itertools
import logging
from collections import defaultdict
from typing import AsyncIterator

from app.core.config import get_settings
from app.core.events import AgentEvent
from app.core.logging import get_logger, log_with_fields

logger = get_logger(__name__)

# 频道前缀,频道形如 run:{agent_run_id}
CHANNEL_PREFIX = "run:"

# 订阅侧重连参数
_RECONNECT_DELAY_S = 1.0
_MAX_RECONNECT_DELAY_S = 10.0
# Pub/Sub 读取超时(秒),用于周期性检查连接健康
_PUBSUB_READ_TIMEOUT_S = 5.0


def channel_for(agent_run_id: str) -> str:
    """返回某次运行对应的事件频道名。"""
    return f"{CHANNEL_PREFIX}{agent_run_id}"


class RedisEventBus:
    """基于 Redis Pub/Sub 的事件总线。

    seq 由进程内按频道维护的计数器分配:发布方应在构造 AgentEvent 时
    先调用 :meth:`next_seq` 取得序号,以保证同一运行内序号单调递增。
    """

    def __init__(self, redis_url: str | None = None) -> None:
        """初始化,延迟创建 Redis 客户端(首次 publish/subscribe 时建立)。"""
        settings = get_settings()
        self._redis_url = redis_url or settings.redis_url
        self._client = None  # type: ignore[var-annotated]
        self._seq_counters: dict[str, itertools.count] = defaultdict(
            lambda: itertools.count(0)
        )

    def next_seq(self, agent_run_id: str) -> int:
        """为某次运行分配下一个单调递增的事件序号(从 0 开始)。"""
        return next(self._seq_counters[agent_run_id])

    def _get_client(self):
        """惰性创建并复用 redis.asyncio 客户端。"""
        if self._client is None:
            # 延迟导入,避免无 redis 依赖的纯逻辑测试受影响
            import redis.asyncio as redis_asyncio

            self._client = redis_asyncio.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def publish(self, channel: str, event: AgentEvent) -> None:
        """向 channel 发布一条事件。失败仅记录日志,不阻断主流程。"""
        try:
            client = self._get_client()
            await client.publish(channel, event.to_json())
        except Exception as exc:  # noqa: BLE001 总线故障不应中断 Agent 运行
            log_with_fields(
                logger,
                logging.ERROR,
                "event_publish_failed",
                channel=channel,
                event_type=event.type.value,
                error=str(exc),
            )

    async def subscribe(self, channel: str) -> AsyncIterator[AgentEvent]:
        """订阅 channel,异步迭代产出 AgentEvent,断线自动重连。

        调用方通过取消该协程(或退出 async for)来结束订阅。
        """
        delay = _RECONNECT_DELAY_S
        while True:
            pubsub = None
            try:
                client = self._get_client()
                pubsub = client.pubsub()
                await pubsub.subscribe(channel)
                delay = _RECONNECT_DELAY_S  # 连接成功,重置退避
                async for event in self._iter_messages(pubsub):
                    yield event
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 重连
                log_with_fields(
                    logger,
                    logging.WARNING,
                    "event_subscribe_reconnect",
                    channel=channel,
                    error=str(exc),
                    retry_in_s=delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, _MAX_RECONNECT_DELAY_S)
            finally:
                await self._safe_close(pubsub, channel)

    async def _iter_messages(self, pubsub) -> AsyncIterator[AgentEvent]:
        """从 pubsub 读取消息并解析为 AgentEvent,跳过非法负载。"""
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=_PUBSUB_READ_TIMEOUT_S,
            )
            if message is None:
                continue
            raw = message.get("data")
            if not raw:
                continue
            try:
                yield AgentEvent.from_json(raw)
            except Exception as exc:  # noqa: BLE001 跳过坏消息
                log_with_fields(
                    logger,
                    logging.WARNING,
                    "event_decode_failed",
                    error=str(exc),
                )

    @staticmethod
    async def _safe_close(pubsub, channel: str) -> None:
        """安全关闭 pubsub 订阅,吞掉关闭期异常。"""
        if pubsub is None:
            return
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
        except Exception:  # noqa: BLE001 关闭失败无需上抛
            pass

    async def close(self) -> None:
        """关闭底层 Redis 客户端。"""
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:  # noqa: BLE001
                pass
            self._client = None


class InMemoryEventBus:
    """进程内事件总线,基于 asyncio.Queue,主要用于测试。

    仅在单进程内有效;publish 会把事件投递到所有当前订阅者的队列。
    """

    def __init__(self) -> None:
        """初始化订阅者表与 seq 计数器。"""
        self._subscribers: dict[str, list[asyncio.Queue[AgentEvent]]] = defaultdict(
            list
        )
        self._seq_counters: dict[str, itertools.count] = defaultdict(
            lambda: itertools.count(0)
        )

    def next_seq(self, agent_run_id: str) -> int:
        """为某次运行分配下一个单调递增的事件序号。"""
        return next(self._seq_counters[agent_run_id])

    async def publish(self, channel: str, event: AgentEvent) -> None:
        """将事件投递给该 channel 的所有订阅者队列。"""
        for queue in list(self._subscribers.get(channel, [])):
            await queue.put(event)

    async def subscribe(self, channel: str) -> AsyncIterator[AgentEvent]:
        """订阅 channel,异步迭代产出事件;退出时自动注销队列。"""
        queue: asyncio.Queue[AgentEvent] = asyncio.Queue()
        self._subscribers[channel].append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            try:
                self._subscribers[channel].remove(queue)
            except ValueError:
                pass


# 进程内单例缓存
_bus_singleton: RedisEventBus | InMemoryEventBus | None = None


def get_event_bus() -> RedisEventBus | InMemoryEventBus:
    """返回进程内事件总线单例。

    默认使用 RedisEventBus;测试可通过 :func:`set_event_bus` 注入内存实现。
    """
    global _bus_singleton
    if _bus_singleton is None:
        _bus_singleton = RedisEventBus()
    return _bus_singleton


def set_event_bus(bus: RedisEventBus | InMemoryEventBus | None) -> None:
    """覆盖/重置进程内事件总线单例(主要供测试使用)。"""
    global _bus_singleton
    _bus_singleton = bus
