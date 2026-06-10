"""运行投递与同步等待网关。

隔离 API 层与 Celery/事件总线的耦合:
- enqueue_run: 通过 Celery 投递 run_agent_task,失败时抛出明确异常。
- await_completion: stream=False 时订阅 EventBus 直至 RUN_COMPLETED/ERROR
  或超时,返回最终事件;用于同步返回结果的场景。

依赖的外部符号(由 tasks 作者提供):app.tasks.celery_app.run_agent_task,
是一个支持 .delay(payload: dict) 的 Celery 任务。导入失败时给出清晰错误。
"""

from __future__ import annotations

import asyncio
import logging

from app.core.events import AgentEvent, EventType
from app.core.interfaces import EventBus
from app.core.logging import get_logger, log_with_fields

logger = get_logger(__name__)

# 同步等待时,单次事件读取的兜底总超时(秒)
_DEFAULT_AWAIT_TIMEOUT = 120.0
# 标记一次运行结束的事件类型
_TERMINAL_TYPES = {EventType.RUN_COMPLETED, EventType.ERROR}


class RunnerUnavailableError(RuntimeError):
    """任务队列不可用(Celery 任务未实现或 broker 异常)。"""


def _load_run_task():
    """惰性加载 Celery run_agent_task,缺失时抛出可读异常。"""
    try:
        # run_agent_task 实际定义在 agent_tasks(celery_app 仅 include 它)
        from app.tasks.agent_tasks import run_agent_task
    except Exception as exc:  # 模块或符号缺失
        raise RunnerUnavailableError(f"无法加载 run_agent_task: {exc}") from exc
    return run_agent_task


def enqueue_run(payload: dict) -> None:
    """将一次运行投递到 Celery 队列。

    payload 至少包含 agent_run_id / conversation_id / trace_id / message。
    投递失败抛出 RunnerUnavailableError,由调用方转换为 503。
    """
    task = _load_run_task()
    try:
        # run_agent_task 的签名是 (agent_run_id, conversation_id, trace_id,
        # user_message) 四个位置参数;payload 用 message 承载用户消息,这里
        # 解包对齐(chat 路由约定的载荷字段)。
        task.delay(
            agent_run_id=payload["agent_run_id"],
            conversation_id=payload["conversation_id"],
            trace_id=payload["trace_id"],
            user_message=payload["message"],
        )
    except Exception as exc:
        log_with_fields(
            logger,
            logging.ERROR,
            "投递 run_agent_task 失败",
            agent_run_id=payload.get("agent_run_id"),
            error=str(exc),
        )
        raise RunnerUnavailableError(f"投递任务失败: {exc}") from exc


async def await_completion(
    bus: EventBus,
    agent_run_id: str,
    timeout_s: float = _DEFAULT_AWAIT_TIMEOUT,
) -> AgentEvent | None:
    """订阅运行频道直至收到终止事件或超时。

    返回最终的 AgentEvent(RUN_COMPLETED/ERROR);超时返回 None。
    """
    channel = f"run:{agent_run_id}"

    async def _consume() -> AgentEvent | None:
        async for event in bus.subscribe(channel):
            if event.type in _TERMINAL_TYPES:
                return event
        return None

    try:
        return await asyncio.wait_for(_consume(), timeout=timeout_s)
    except asyncio.TimeoutError:
        log_with_fields(
            logger,
            logging.WARNING,
            "同步等待运行结果超时",
            agent_run_id=agent_run_id,
            timeout_s=timeout_s,
        )
        return None
