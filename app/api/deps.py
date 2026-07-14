"""FastAPI 依赖注入。

集中提供请求级依赖:当前用户、仓储、事件总线、限流器。
所有有状态资源(redis/db)均按请求获取或经 app.state 暴露的单例访问,
保证 API 层本身无状态。
"""

from __future__ import annotations

from typing import Annotated, AsyncIterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.repos import Repos
from app.api.ratelimit import RateLimiter
from app.core.interfaces import EventBus
from app.core.logging import get_logger
from app.db.session import get_session

logger = get_logger(__name__)

async def get_current_user(request: Request) -> str:
    """Return only the owner already validated by authentication middleware."""
    state_user = getattr(request.state, "user_id", None)
    if state_user:
        return state_user
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="MARKETPLACE_IDENTITY_REQUIRED",
    )


async def get_repos(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AsyncIterator[Repos]:
    """提供绑定到当前请求会话的仓储聚合。"""
    yield Repos(session)


def get_event_bus(request: Request) -> EventBus:
    """返回 app.state 上的事件总线单例。

    事件总线在应用 lifespan 启动时初始化;缺失说明应用未就绪。
    """
    bus = getattr(request.app.state, "event_bus", None)
    if bus is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="事件总线尚未就绪",
        )
    return bus


def get_rate_limiter(request: Request) -> RateLimiter:
    """返回 app.state 上的限流器单例。"""
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="限流器尚未就绪",
        )
    return limiter


CurrentUser = Annotated[str, Depends(get_current_user)]
ReposDep = Annotated[Repos, Depends(get_repos)]
EventBusDep = Annotated[EventBus, Depends(get_event_bus)]
RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]
