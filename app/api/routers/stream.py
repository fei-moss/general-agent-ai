"""流式网关路由:SSE 与 WebSocket。

- GET /stream/{agent_run_id}: 用 sse-starlette 订阅 EventBus 频道 run:{id},
  将 AgentEvent 逐条以 SSE 推送,收到 RUN_COMPLETED/ERROR 后结束。
- WS /ws/{agent_run_id}: 等价的 WebSocket 推送。

两者都从同一事件总线读取,API 层不缓存事件,断线后客户端可重连重订阅。
WebSocket 不经 HTTP 中间件,故在握手阶段自行做轻量鉴权。
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_event_bus
from app.core.events import AgentEvent, EventType
from app.core.interfaces import EventBus
from app.core.logging import get_logger, log_with_fields, set_trace_id

logger = get_logger(__name__)

router = APIRouter(tags=["stream"])

# 终止事件:收到后结束流
_TERMINAL_TYPES = {EventType.RUN_COMPLETED, EventType.ERROR}


def _channel(agent_run_id: str) -> str:
    """运行对应的事件总线频道名。"""
    return f"run:{agent_run_id}"


@router.get("/stream/{agent_run_id}")
async def stream_sse(
    agent_run_id: str,
    request: Request,
    bus: EventBus = Depends(get_event_bus),
) -> EventSourceResponse:
    """SSE 端点:逐条推送事件直至终止或客户端断开。"""

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        channel = _channel(agent_run_id)
        try:
            async for event in bus.subscribe(channel):
                if await request.is_disconnected():
                    break
                yield event.to_sse()
                if event.type in _TERMINAL_TYPES:
                    break
        except Exception as exc:  # 订阅异常:发一条 error 事件后收尾
            log_with_fields(
                logger,
                logging.ERROR,
                "SSE 订阅异常",
                agent_run_id=agent_run_id,
                error=str(exc),
            )
            yield {"event": EventType.ERROR.value, "data": str(exc)}

    return EventSourceResponse(event_generator())


@router.websocket("/ws/{agent_run_id}")
async def stream_ws(websocket: WebSocket, agent_run_id: str) -> None:
    """WebSocket 端点:等价于 SSE 的事件推送。"""
    bus = getattr(websocket.app.state, "event_bus", None)
    if bus is None:
        await websocket.close(code=1011, reason="事件总线未就绪")
        return
    if not _ws_authorized(websocket):
        await websocket.close(code=1008, reason="缺少鉴权凭证")
        return
    await websocket.accept()
    await _pump_ws(websocket, bus, agent_run_id)


def _ws_authorized(websocket: WebSocket) -> bool:
    """WebSocket 轻量鉴权:校验 query token 或 header。"""
    token = websocket.query_params.get("token")
    if token:
        return True
    auth = websocket.headers.get("authorization")
    api_key = websocket.headers.get("x-api-key")
    return bool(auth or api_key)


async def _pump_ws(websocket: WebSocket, bus: EventBus, agent_run_id: str) -> None:
    """从事件总线读取并通过 WS 推送,处理断开与异常。"""
    channel = _channel(agent_run_id)
    try:
        async for event in bus.subscribe(channel):
            await websocket.send_text(_ws_payload(event))
            if event.type in _TERMINAL_TYPES:
                break
    except WebSocketDisconnect:
        log_with_fields(
            logger, logging.INFO, "WS 客户端断开", agent_run_id=agent_run_id
        )
    except Exception as exc:
        log_with_fields(
            logger,
            logging.ERROR,
            "WS 推送异常",
            agent_run_id=agent_run_id,
            error=str(exc),
        )
    finally:
        set_trace_id(None)
        await _safe_close(websocket)


def _ws_payload(event: AgentEvent) -> str:
    """WS 帧采用与 Pub/Sub 一致的事件 JSON。"""
    return event.to_json()


async def _safe_close(websocket: WebSocket) -> None:
    """安全关闭 WS,忽略已关闭导致的异常。"""
    try:
        await websocket.close()
    except Exception:  # 已关闭:忽略
        pass
