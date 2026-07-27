"""Agent 运行状态持久化辅助。

封装 worker 侧对 AgentRun / TaskState 的状态读写,供 agent_tasks 使用。
所有函数都在独立的 AsyncSession 中执行并自行提交,失败时回滚。
状态写入失败必须上抛给 worker/runner,避免业务成功越过持久化失败。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.enums import IntentType, RunStatus, TaskStatus
from app.core.ids import new_run_id
from app.core.logging import get_logger, log_with_fields
from app.core.secrets import redact_runtime_error
from app.core.models import AgentRun, TaskState
from app.db.session import async_session_factory
from app.db.state_machine import (
    assert_run_transition,
    assert_task_transition,
    is_terminal_run_status,
)

logger = get_logger(__name__)


def _utcnow() -> datetime:
    """返回带时区的当前 UTC 时间。"""
    return datetime.now(timezone.utc)


async def ensure_run(
    agent_run_id: str, conversation_id: str, trace_id: str
) -> None:
    """确保 AgentRun 行存在;不存在则创建为 PENDING。幂等。"""
    try:
        async with async_session_factory() as session:
            existing = await session.get(AgentRun, agent_run_id)
            if existing is not None:
                return
            session.add(
                AgentRun(
                    id=agent_run_id,
                    conversation_id=conversation_id,
                    trace_id=trace_id,
                    status=RunStatus.PENDING,
                )
            )
            await session.commit()
    except Exception as exc:
        _log_store_error("ensure_run_failed", agent_run_id, exc)
        raise


async def mark_run_running(
    agent_run_id: str,
    *,
    task_id: str | None = None,
    attempt: int = 0,
) -> None:
    """将运行置为 RUNNING 并写入 started_at。"""
    await _update_run_and_task(
        agent_run_id,
        run_status=RunStatus.RUNNING,
        task_id=task_id,
        task_status=TaskStatus.RUNNING,
        attempt=attempt,
        started_at=_utcnow(),
    )


async def mark_run_succeeded(
    agent_run_id: str,
    intent: IntentType | None = None,
    *,
    task_id: str | None = None,
) -> None:
    """将运行置为 SUCCEEDED 并写入 finished_at(可选回填 intent)。"""
    fields: dict[str, Any] = {
        "finished_at": _utcnow(),
    }
    if intent is not None:
        fields["intent"] = intent
    await _update_run_and_task(
        agent_run_id,
        run_status=RunStatus.SUCCEEDED,
        task_id=task_id,
        task_status=TaskStatus.DONE,
        **fields,
    )


async def mark_run_failed(
    agent_run_id: str,
    error: str,
    *,
    task_id: str | None = None,
) -> None:
    """将运行置为 FAILED,写入截断后的错误信息与 finished_at。"""
    await _update_run_and_task(
        agent_run_id,
        run_status=RunStatus.FAILED,
        task_id=task_id,
        task_status=TaskStatus.ERROR,
        error=error[:2000],
        finished_at=_utcnow(),
        task_result={"error": error[:2000]},
    )


async def mark_task_queued_for_retry(
    task_id: str,
    agent_run_id: str,
    *,
    attempt: int,
    error: str,
) -> None:
    """Return a non-terminal task to QUEUED without terminalizing its run."""
    try:
        async with async_session_factory() as session:
            run = await session.get(AgentRun, agent_run_id)
            if run is None or is_terminal_run_status(run.status):
                return
            task = await session.get(TaskState, task_id)
            if task is None or task.status in {TaskStatus.DONE, TaskStatus.ERROR}:
                return
            assert_task_transition(task.status, TaskStatus.QUEUED)
            task.status = TaskStatus.QUEUED
            task.attempt = max(int(task.attempt or 0), int(attempt))
            task.result = {"retry_error": error[:2000]}
            task.updated_at = _utcnow()
            await session.commit()
    except Exception as exc:
        _log_store_error("queue_task_retry_failed", agent_run_id, exc)
        raise


async def _update_run_and_task(
    agent_run_id: str,
    *,
    run_status: RunStatus,
    task_id: str | None,
    task_status: TaskStatus | None,
    attempt: int | None = None,
    task_result: dict[str, Any] | None = None,
    **fields: Any,
) -> None:
    """Atomically converge AgentRun and its queue TaskState."""
    try:
        async with async_session_factory() as session:
            run = await session.get(AgentRun, agent_run_id)
            if run is None:
                raise RuntimeError(f"AgentRun not found: {agent_run_id}")
            if is_terminal_run_status(run.status) and run.status != run_status:
                return
            assert_run_transition(run.status, run_status)
            run.status = run_status
            for key, value in fields.items():
                setattr(run, key, value)
            if task_id is not None and task_status is not None:
                task = await session.get(TaskState, task_id)
                if task is None:
                    raise RuntimeError(f"TaskState not found: {task_id}")
                if task.status != task_status:
                    assert_task_transition(task.status, task_status)
                    task.status = task_status
                if attempt is not None:
                    task.attempt = max(int(task.attempt or 0), int(attempt))
                if task_result is not None:
                    task.result = task_result
                task.updated_at = _utcnow()
            await session.commit()
    except Exception as exc:
        _log_store_error("update_run_failed", agent_run_id, exc)
        raise


async def upsert_task(
    agent_run_id: str,
    task_type: str,
    status,
    *,
    attempt: int = 0,
    payload: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
) -> None:
    """插入一条 TaskState 记录(每次调用插入新行,便于审计每步状态)。"""
    try:
        async with async_session_factory() as session:
            session.add(
                TaskState(
                    id=new_run_id(),
                    agent_run_id=agent_run_id,
                    task_type=task_type,
                    status=status,
                    attempt=attempt,
                    payload=payload,
                    result=result,
                )
            )
            await session.commit()
    except Exception as exc:
        _log_store_error("upsert_task_failed", agent_run_id, exc)
        raise


def _log_store_error(event: str, agent_run_id: str, exc: Exception) -> None:
    """统一记录持久化错误。"""
    log_with_fields(
        logger,
        logging.ERROR,
        event,
        agent_run_id=agent_run_id,
        error=redact_runtime_error(f"{type(exc).__name__}: {exc}"),
    )
