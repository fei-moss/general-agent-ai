"""核心对话入口路由。

POST /chat 流程:
1. 鉴权/限流由中间件完成,此处校验请求体(Pydantic)。
2. 创建或复用 conversation,写入用户消息。
3. 生成 agent_run_id + trace_id,落库 AgentRun(PENDING) + TaskState(QUEUED)。
4. 投递 Celery run_agent_task。
5. 立即返回 ChatAccepted(含 stream_url / ws_url)。
   stream=False 时改为订阅事件总线同步等待最终结果。

API 层无状态:不在内存保存会话,全部经 DB/Redis。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUser, EventBusDep, ReposDep
from app.api.runner_gateway import (
    RunnerUnavailableError,
    await_completion,
    enqueue_run,
)
from app.core.enums import MessageRole, RunStatus
from app.core.events import EventType
from app.core.ids import _new_id, new_run_id, new_trace_id
from app.core.logging import get_logger, log_with_fields
from app.core.schemas import ChatAccepted, ChatRequest

logger = get_logger(__name__)

router = APIRouter(tags=["chat"])

# 投递任务的子任务类型(对应 task_state.task_type)
_RUN_TASK_TYPE = "run"


@router.post("/chat", status_code=status.HTTP_202_ACCEPTED)
async def create_chat(
    body: ChatRequest,
    request: Request,
    user: CurrentUser,
    repos: ReposDep,
    bus: EventBusDep,
) -> Any:
    """受理一次对话/任务请求。"""
    _validate_message(body.message)
    trace_id = getattr(request.state, "trace_id", None) or new_trace_id()
    run_id = new_run_id()

    conversation = await repos.ensure_conversation(body.conversation_id, user)
    await repos.add_message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=body.message,
    )
    await repos.create_run(run_id, conversation.id, trace_id)
    payload = _build_payload(run_id, conversation.id, trace_id, body)
    await repos.create_queued_task(
        task_id=_new_id("task_"),
        agent_run_id=run_id,
        task_type=_RUN_TASK_TYPE,
        payload=payload,
    )
    await repos.commit()

    _dispatch(payload)

    if not body.stream:
        return await _wait_sync(bus, run_id, conversation.id, trace_id)
    return _accepted(conversation.id, run_id, trace_id)


def _validate_message(message: str) -> None:
    """校验消息非空,空白消息直接 422。"""
    if not message or not message.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="message 不能为空",
        )


def _build_payload(
    run_id: str, conversation_id: str, trace_id: str, body: ChatRequest
) -> dict[str, Any]:
    """组装投递给 Celery 的任务载荷。"""
    return {
        "agent_run_id": run_id,
        "conversation_id": conversation_id,
        "trace_id": trace_id,
        "message": body.message,
        "metadata": body.metadata,
    }


def _dispatch(payload: dict[str, Any]) -> None:
    """投递任务,队列不可用时转换为 503。"""
    try:
        enqueue_run(payload)
    except RunnerUnavailableError as exc:
        log_with_fields(
            logger,
            logging.ERROR,
            "任务队列不可用",
            agent_run_id=payload["agent_run_id"],
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="任务队列暂不可用,请稍后重试",
        ) from exc


def _accepted(conversation_id: str, run_id: str, trace_id: str) -> ChatAccepted:
    """构造 202 受理响应。"""
    return ChatAccepted(
        conversation_id=conversation_id,
        agent_run_id=run_id,
        trace_id=trace_id,
        status=RunStatus.PENDING,
        stream_url=f"/stream/{run_id}",
        ws_url=f"/ws/{run_id}",
    )


async def _wait_sync(bus, run_id: str, conversation_id: str, trace_id: str) -> Any:
    """stream=False:订阅事件总线等待运行结束,返回最终结果或 504。"""
    final_event = await await_completion(bus, run_id)
    if final_event is None:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="等待运行结果超时",
        )
    # RUN_COMPLETED 在成功与失败时都会发出,需进一步看 data.status;
    # ERROR 终止事件直接视为失败。
    succeeded = (
        final_event.type == EventType.RUN_COMPLETED
        and final_event.data.get("status") == RunStatus.SUCCEEDED.value
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK if succeeded else status.HTTP_502_BAD_GATEWAY,
        content={
            "agent_run_id": run_id,
            "conversation_id": conversation_id,
            "trace_id": trace_id,
            "status": RunStatus.SUCCEEDED.value
            if succeeded
            else RunStatus.FAILED.value,
            "result": final_event.data,
        },
    )
