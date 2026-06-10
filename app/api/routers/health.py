"""健康检查路由。

- /healthz: 存活探针,进程在即返回 200。
- /readyz: 就绪探针,校验数据库与事件总线是否可用,任一失败返回 503。
"""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.logging import get_logger
from app.db.session import async_session_factory

logger = get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """存活探针:只要进程响应即视为存活。"""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request) -> JSONResponse:
    """就绪探针:校验 DB 与事件总线连通性。"""
    checks: dict[str, str] = {}
    db_ok = await _check_db(checks)
    bus_ok = _check_bus(request, checks)
    ready = db_ok and bus_ok
    code = status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=code,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )


async def _check_db(checks: dict[str, str]) -> bool:
    """执行 SELECT 1 验证数据库可用。"""
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["db"] = "ok"
        return True
    except Exception as exc:
        checks["db"] = f"error: {exc}"
        return False


def _check_bus(request: Request, checks: dict[str, str]) -> bool:
    """校验事件总线单例是否已初始化。"""
    bus = getattr(request.app.state, "event_bus", None)
    if bus is None:
        checks["event_bus"] = "not_initialized"
        return False
    checks["event_bus"] = "ok"
    return True
