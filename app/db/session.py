"""异步数据库会话工厂。

提供进程级 async engine 与 async_sessionmaker,并暴露 get_session 作为
FastAPI 依赖,确保每个请求获得独立会话且用后即关。
"""

from __future__ import annotations

from typing import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.metrics import Metrics

_metrics = Metrics()


def _create_engine() -> AsyncEngine:
    """根据配置创建异步引擎。"""
    settings = get_settings()
    engine = create_async_engine(
        settings.db_url,
        echo=False,
        future=True,
        **_engine_options_from_settings(settings),
    )
    _install_pool_metrics(engine)
    return engine


def _engine_options_from_settings(settings) -> dict[str, object]:
    """Return explicit SQLAlchemy pool options from settings."""
    return {
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_pre_ping": settings.db_pool_pre_ping,
        "pool_recycle": settings.db_pool_recycle_s,
    }


def _install_pool_metrics(engine: AsyncEngine) -> None:
    """Install no-op safe pool metric hooks."""

    @event.listens_for(engine.sync_engine, "checkout")
    def _checkout(dbapi_connection, connection_record, connection_proxy) -> None:
        _metrics.inc_counter("db_pool_checkouts_total")
        _metrics.observe_histogram("db_pool_checkout_seconds", 0.0)

    @event.listens_for(engine.sync_engine, "checkin")
    def _checkin(dbapi_connection, connection_record) -> None:
        _metrics.set_gauge("db_streaming_phase_connections", 0)


# 进程级单例
engine: AsyncEngine = _create_engine()

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖:产出一个会话,请求结束后自动关闭。"""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """关闭引擎连接池(应用关闭时调用)。"""
    await engine.dispose()
