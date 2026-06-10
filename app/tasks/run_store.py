"""Agent 运行状态持久化辅助。

封装 worker 侧对 AgentRun / TaskState 的状态读写,供 agent_tasks 使用。
所有函数都在独立的 AsyncSession 中执行并自行提交,失败时回滚。
为了不阻断 Agent 主流程,写状态失败仅记录日志、不上抛。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.enums import IntentType, RunStatus
from app.core.ids import new_run_id
from app.core.logging import get_logger, log_with_fields
from app.core.models import AgentRun, TaskState
from app.db.session import async_session_factory

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
    except Exception as exc:  # noqa: BLE001 状态写入失败不应中断运行
        _log_store_error("ensure_run_failed", agent_run_id, exc)


async def mark_run_running(agent_run_id: str) -> None:
    """将运行置为 RUNNING 并写入 started_at。"""
    await _update_run(
        agent_run_id, status=RunStatus.RUNNING, started_at=_utcnow()
    )


async def mark_run_succeeded(
    agent_run_id: str, intent: IntentType | None = None
) -> None:
    """将运行置为 SUCCEEDED 并写入 finished_at(可选回填 intent)。"""
    fields: dict[str, Any] = {
        "status": RunStatus.SUCCEEDED,
        "finished_at": _utcnow(),
    }
    if intent is not None:
        fields["intent"] = intent
    await _update_run(agent_run_id, **fields)


async def mark_run_failed(agent_run_id: str, error: str) -> None:
    """将运行置为 FAILED,写入截断后的错误信息与 finished_at。"""
    await _update_run(
        agent_run_id,
        status=RunStatus.FAILED,
        error=error[:2000],
        finished_at=_utcnow(),
    )


async def _update_run(agent_run_id: str, **fields: Any) -> None:
    """通用的 AgentRun 字段更新(不存在则跳过)。"""
    try:
        async with async_session_factory() as session:
            run = await session.get(AgentRun, agent_run_id)
            if run is None:
                log_with_fields(
                    logger,
                    logging.WARNING,
                    "update_run_missing",
                    agent_run_id=agent_run_id,
                )
                return
            for key, value in fields.items():
                setattr(run, key, value)
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        _log_store_error("update_run_failed", agent_run_id, exc)


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
    except Exception as exc:  # noqa: BLE001
        _log_store_error("upsert_task_failed", agent_run_id, exc)


def _log_store_error(event: str, agent_run_id: str, exc: Exception) -> None:
    """统一记录持久化错误。"""
    log_with_fields(
        logger,
        logging.ERROR,
        event,
        agent_run_id=agent_run_id,
        error=str(exc),
    )
