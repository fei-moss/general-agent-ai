"""异步数据库会话工厂。

提供进程级 async engine 与 async_sessionmaker,并暴露 get_session 作为
FastAPI 依赖,确保每个请求获得独立会话且用后即关。
"""

from __future__ import annotations

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def _create_engine() -> AsyncEngine:
    """根据配置创建异步引擎。"""
    settings = get_settings()
    return create_async_engine(
        settings.db_url,
        echo=False,
        pool_pre_ping=True,
        future=True,
    )


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
