"""应用生命周期资源装配。

在 FastAPI lifespan 中初始化与释放共享单例:
- redis 客户端(限流 + 事件总线后端)
- event_bus(必须使用可回放 Redis Stream 实现)
- rate_limiter(基于上面的 redis)

所有单例挂在 app.state,供依赖与中间件读取,保证 API 层无状态。
依赖的外部符号:app.bus.create_event_bus(redis_url: str) -> EventBus。
构造失败时启动失败,避免生产静默退回不可回放的 Pub/Sub 或空总线。
"""

from __future__ import annotations

import contextlib
from typing import AsyncIterator

from fastapi import FastAPI
from redis.asyncio import Redis

from app.api.ratelimit import RateLimiter
from app.core.config import get_settings
from app.core.interfaces import EventBus
from app.core.logging import configure_logging, get_logger
from app.core.metrics import Metrics
from app.core.secrets import build_secret_provider
from app.runtime.locks import ConversationLock, RunLease
from app.runtime.provider_keys import build_provider_key_pool
from app.runtime.provider_limits import (
    build_provider_limiter,
    provider_identity_from_settings,
)
from app.runtime.runner import RealtimeRunner

logger = get_logger(__name__)


def _build_event_bus(redis_url: str, redis_client=None, metrics: Metrics | None = None) -> EventBus:
    """构造唯一受支持的 Redis Stream 事件总线。"""
    from app.bus import create_event_bus

    bus = create_event_bus(redis_url, redis_client=redis_client, metrics=metrics)
    if not hasattr(bus, "replay"):
        raise RuntimeError("event bus must support Redis Stream replay")
    return bus


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """初始化与释放应用级共享资源。"""
    settings = get_settings()
    configure_logging(settings.log_level)
    metrics = Metrics()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    event_bus = _build_event_bus(settings.redis_url, redis, metrics)
    secret_provider = build_secret_provider(settings)
    identity = provider_identity_from_settings(settings)
    provider_key_pool = build_provider_key_pool(settings, secret_provider)
    if provider_key_pool.status == "missing" or (
        not identity.mock and not provider_key_pool.enabled_slots
    ):
        secret_provider.validate_required(identity.provider, identity.model)
    provider_limiter = build_provider_limiter(
        settings,
        redis_client=redis,
        metrics=metrics,
        secret_provider=secret_provider,
        key_pool=provider_key_pool,
    )
    app.state.redis = redis
    app.state.metrics = metrics
    app.state.event_bus = event_bus
    app.state.secret_provider = secret_provider
    app.state.provider_key_pool = provider_key_pool
    app.state.provider_limiter = provider_limiter
    app.state.rate_limiter = RateLimiter(
        redis, settings.rate_limit_per_min, metrics=metrics
    )
    app.state.conversation_lock = ConversationLock(redis_client=redis)
    app.state.realtime_runner = _build_realtime_runner(
        redis, event_bus, settings, provider_limiter, secret_provider, metrics
    )
    logger.info("API 启动完成")
    try:
        yield
    finally:
        await _shutdown(app, redis)


async def _shutdown(app: FastAPI, redis: Redis) -> None:
    """优雅释放 redis 与数据库连接池。"""
    with contextlib.suppress(Exception):
        await redis.aclose()
    with contextlib.suppress(Exception):
        from app.db.session import dispose_engine

        await dispose_engine()
    logger.info("API 已关闭")


def _build_realtime_runner(
    redis, event_bus: EventBus, settings, provider_limiter, secret_provider, metrics
) -> RealtimeRunner:
    """Build the per-process realtime runner with shared Redis-backed deps."""

    def orchestrator_factory():
        from app.runtime.deps import build_deps
        from app.runtime.orchestrator import AgentOrchestrator

        return AgentOrchestrator(
            build_deps(
                event_bus=event_bus,
                redis_client=redis,
                provider_limiter=provider_limiter,
                secret_provider=secret_provider,
                metrics=metrics,
            )
        )

    return RealtimeRunner(
        orchestrator_factory=orchestrator_factory,
        run_lease=RunLease(redis_client=redis),
        max_concurrency=settings.realtime_runner_max_concurrency,
        max_runtime_s=settings.run_max_runtime_s,
        metrics=metrics,
        event_bus=event_bus,
        secret_provider=secret_provider,
    )
