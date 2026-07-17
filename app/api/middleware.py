"""请求中间件:鉴权、限流、trace_id 注入。

职责:
- 鉴权:所有用户侧 Chat 路由只接受 Marketplace 专用头提供的可信 wallet owner;
  `/rag/*` 继续使用独立的内部管理员身份契约。
- 限流:对写入类路径按 user_id 做滑动窗口限流,超限 429。
- trace_id:每请求生成或透传 X-Trace-Id,注入日志上下文并回写响应头。

中间件保持无状态:仅依赖请求头与 app.state 上的共享单例(限流器)。
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.api.identity import IdentityResolutionError, resolve_http_identity
from app.core.ids import new_trace_id
from app.core.logging import get_logger, log_with_fields, set_trace_id

logger = get_logger(__name__)

_TRACE_HEADER = "X-Trace-Id"
_REMOVED_VERSIONED_CHAT_PREFIX = "/api/v1/chat"

# 无需鉴权即可访问的路径前缀(健康检查与文档)
_PUBLIC_PREFIXES = (
    "/healthz",
    "/readyz",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
)
# 需要执行限流的路径(写入/触发类)。
_RATE_LIMITED_PREFIXES = ("/chat",)


def _is_public(path: str) -> bool:
    """判断路径是否豁免鉴权。"""
    return any(path.startswith(p) for p in _PUBLIC_PREFIXES)


def _is_removed_versioned_chat(path: str) -> bool:
    """误加的 /api/v1/chat 路由族不做鉴权拦截,交给 router 返回 404。"""
    return path == _REMOVED_VERSIONED_CHAT_PREFIX or path.startswith(
        f"{_REMOVED_VERSIONED_CHAT_PREFIX}/"
    )


def _needs_rate_limit(path: str) -> bool:
    """判断路径是否需要限流。"""
    return any(path.startswith(p) for p in _RATE_LIMITED_PREFIXES)


class TraceIdMiddleware(BaseHTTPMiddleware):
    """为每个请求建立 trace_id 上下文并回写响应头。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        """注入 trace_id,调用下游,并在响应头透出。"""
        trace_id = request.headers.get(_TRACE_HEADER) or new_trace_id()
        request.state.trace_id = trace_id
        set_trace_id(trace_id)
        try:
            response = await call_next(request)
        finally:
            # 请求结束后清理上下文,避免污染后续协程
            set_trace_id(None)
        response.headers[_TRACE_HEADER] = trace_id
        return response


class AuthMiddleware(BaseHTTPMiddleware):
    """鉴权中间件:受保护路径缺失凭证返回 401。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        """解析并校验 user_id。"""
        if _is_public(request.url.path) or _is_removed_versioned_chat(request.url.path):
            return await call_next(request)
        try:
            identity = resolve_http_identity(request)
        except IdentityResolutionError as exc:
            return _json_error(exc.status_code, exc.detail)
        request.state.user_id = identity.owner_id
        request.state.user_id_source = identity.source
        request.state.marketplace_identity = identity
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """限流中间件:对写入类路径按 user_id 滑动窗口限流。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        """超过阈值返回 429,并附带 Retry-After 头。"""
        if not _needs_rate_limit(request.url.path):
            return await call_next(request)
        limiter = getattr(request.app.state, "rate_limiter", None)
        user_id = getattr(request.state, "user_id", None)
        if limiter is None or not user_id:
            # 限流器未就绪或匿名:不阻断,交由下游处理
            return await call_next(request)
        result = await limiter.check(user_id, route=request.url.path)
        if not result.allowed:
            log_with_fields(
                logger,
                logging.WARNING,
                "请求被限流",
                limit=result.limit,
                identity_source=getattr(request.state, "user_id_source", "unknown"),
            )
            return _rate_limit_response(result)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        return response


def _json_error(status_code: int, detail: str) -> JSONResponse:
    """统一的 JSON 错误响应体。"""
    return JSONResponse(status_code=status_code, content={"detail": detail})


def _rate_limit_response(result) -> JSONResponse:
    """构造 429 响应,附带限流相关头。"""
    response = _json_error(429, "请求过于频繁,请稍后再试")
    response.headers["Retry-After"] = str(result.retry_after)
    response.headers["X-RateLimit-Limit"] = str(result.limit)
    response.headers["X-RateLimit-Remaining"] = "0"
    return response
