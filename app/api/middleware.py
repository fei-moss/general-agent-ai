"""请求中间件:鉴权、限流、trace_id 注入。

职责:
- 鉴权:chat-flow 路由优先从 URL user_uuid 取 user_id;
  缺失时从 Authorization Bearer 或 X-API-Key 取兼容 user_id。
- 限流:对写入类路径按 user_id 做滑动窗口限流,超限 429。
- trace_id:每请求生成或透传 X-Trace-Id,注入日志上下文并回写响应头。

中间件保持无状态:仅依赖请求头与 app.state 上的共享单例(限流器)。
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.ids import new_trace_id
from app.core.logging import get_logger, log_with_fields, set_trace_id

logger = get_logger(__name__)

_BEARER_PREFIX = "Bearer "
_TRACE_HEADER = "X-Trace-Id"
_URL_USER_QUERY = "user_uuid"
_MAX_USER_ID_LENGTH = 64
_ID_SOURCE_URL_USER_UUID = "user_uuid"
_ID_SOURCE_HEADER = "header"
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
# chat-flow 路由允许 URL user_uuid 作为上游身份。/conversations 仍按 header
# 鉴权,避免把 query identity 扩散到非本次契约范围。
_CHAT_FLOW_PATHS = ("/chat",)
_CHAT_FLOW_PREFIXES = ("/stream/", "/ws/", "/runs/")

# 需要执行限流的路径(写入/触发类)。
_RATE_LIMITED_PREFIXES = ("/chat",)


def _extract_user_identity(request: Request) -> tuple[str | None, str | None]:
    """解析 user_id 及来源,缺失返回 (None, None)。"""
    if _is_chat_flow(request.url.path):
        user_uuid = request.query_params.get(_URL_USER_QUERY)
        if user_uuid is not None:
            stripped = user_uuid.strip()
            return (stripped or None), _ID_SOURCE_URL_USER_UUID
    auth = request.headers.get("authorization")
    if auth and auth.startswith(_BEARER_PREFIX):
        token = auth[len(_BEARER_PREFIX) :].strip()
        if token:
            return token, _ID_SOURCE_HEADER
    api_key = request.headers.get("x-api-key")
    if api_key and api_key.strip():
        return api_key.strip(), _ID_SOURCE_HEADER
    return None, None


def _is_public(path: str) -> bool:
    """判断路径是否豁免鉴权。"""
    return any(path.startswith(p) for p in _PUBLIC_PREFIXES)


def _is_removed_versioned_chat(path: str) -> bool:
    """误加的 /api/v1/chat 路由族不做鉴权拦截,交给 router 返回 404。"""
    return path == _REMOVED_VERSIONED_CHAT_PREFIX or path.startswith(
        f"{_REMOVED_VERSIONED_CHAT_PREFIX}/"
    )


def _is_chat_flow(path: str) -> bool:
    """判断是否为本次 user_uuid 契约覆盖的现有 chat-flow 路由。"""
    return path in _CHAT_FLOW_PATHS or any(path.startswith(p) for p in _CHAT_FLOW_PREFIXES)


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
        user_id, source = _extract_user_identity(request)
        if not user_id:
            detail = (
                "缺少 user_uuid"
                if source == _ID_SOURCE_URL_USER_UUID
                else "缺少鉴权凭证(Authorization Bearer 或 X-API-Key)"
            )
            return _json_error(401, detail)
        if len(user_id) > _MAX_USER_ID_LENGTH:
            detail = (
                "USER_UUID_TOO_LONG"
                if source == _ID_SOURCE_URL_USER_UUID
                else "USER_ID_TOO_LONG"
            )
            return _json_error(422, detail)
        request.state.user_id = user_id
        request.state.user_id_source = source
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
                user_id=user_id,
                limit=result.limit,
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
