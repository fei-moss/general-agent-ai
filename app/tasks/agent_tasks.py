"""Agent 编排的 Celery 任务入口。

``run_agent_task`` 是 worker 的主入口:在同步任务体内通过 async 桥接运行
异步编排流程,全程向事件总线发布 AgentEvent,并维护 AgentRun/TaskState
状态。任何异常都会被捕获 -> 发布 ERROR 事件 + 置 run 为 FAILED,并按
配置进行有限次重试(acks_late 已在 celery_app 中开启)。

与 app/runtime 的集成契约(由 runtime 作者实现):

    async def run_orchestration(
        *, agent_run_id, conversation_id, trace_id,
        user_message, emit,
    ) -> dict

其中 ``emit`` 为本模块注入的协程回调:``await emit(event_type, data)``,
负责自动分配 seq、构造 AgentEvent 并发布到 run:{agent_run_id} 频道。
若 runtime 无法加载,任务按有限重试和最终 FAILED 语义收敛。
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from celery import shared_task

from app.bus.event_bus import channel_for, get_event_bus
from app.core.enums import RunStatus
from app.core.events import AgentEvent, EventType
from app.core.logging import get_logger, log_with_fields, set_trace_id
from app.core.secrets import redact_runtime_error
from app.tasks import run_store
from app.tasks.async_bridge import run_coro
from app.tasks.celery_app import RETRY_KWARGS
from app.runtime.provider_limits import ProviderRateLimitError

logger = get_logger(__name__)

# emit 回调类型:emit(event_type, data) -> None
EmitFn = Callable[[EventType, dict[str, Any]], Awaitable[None]]


def _make_emitter(bus, agent_run_id: str, trace_id: str) -> EmitFn:
    """构造向 run:{agent_run_id} 频道发布事件的 emit 回调。

    自动分配单调递增 seq 并填充 trace_id,屏蔽底层总线细节。
    """
    channel = channel_for(agent_run_id)

    async def emit(event_type: EventType, data: dict[str, Any]) -> None:
        event = AgentEvent(
            agent_run_id=agent_run_id,
            trace_id=trace_id,
            type=event_type,
            seq=bus.next_seq(agent_run_id),
            data=data or {},
        )
        await bus.publish(channel, event)

    return emit


def _resolve_orchestrator():
    """解析真实 orchestrator；缺失时让 worker 的失败/重试边界接管。"""
    from app.runtime.orchestrator import run_orchestration

    return run_orchestration


async def _execute(
    agent_run_id: str,
    conversation_id: str,
    trace_id: str,
    user_message: str,
    task_id: str | None = None,
    attempt: int = 0,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    run_context: dict[str, Any] | None = None,
    marketplace_viewer_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """异步执行完整编排:状态流转 + 事件发布 + 调用 orchestrator。"""
    set_trace_id(trace_id)
    bus = get_event_bus()
    emit = _make_emitter(bus, agent_run_id, trace_id)
    orchestrate = _resolve_orchestrator()

    await run_store.ensure_run(agent_run_id, conversation_id, trace_id)
    await run_store.mark_run_running(
        agent_run_id,
        task_id=task_id,
        attempt=attempt,
    )
    # 生命周期事件(RUN_STARTED/RUN_COMPLETED)统一由 AgentOrchestrator 发布,
    # 此处不再重复发射,
    # 避免同一频道出现重复的生命周期事件;run_store 仅做任务侧状态记账。
    result = await orchestrate(
        agent_run_id=agent_run_id,
        conversation_id=conversation_id,
        trace_id=trace_id,
        user_message=user_message,
        emit=emit,
        user_id=user_id,
        metadata=metadata or {},
        run_context=run_context or {},
        marketplace_viewer_context=marketplace_viewer_context,
    )

    intent = (result or {}).get("intent")
    if (result or {}).get("status") == RunStatus.FAILED.value:
        await run_store.mark_run_failed(
            agent_run_id,
            str((result or {}).get("error") or "ORCHESTRATION_FAILED"),
            task_id=task_id,
        )
        return result or {}
    await run_store.mark_run_succeeded(
        agent_run_id,
        intent=intent,
        task_id=task_id,
    )
    return result or {}


async def _publish_error(
    agent_run_id: str,
    trace_id: str,
    error: str,
    *,
    task_id: str | None = None,
) -> None:
    """发布 ERROR 事件并把运行置为 FAILED。"""
    bus = get_event_bus()
    emit = _make_emitter(bus, agent_run_id, trace_id)
    await emit(EventType.ERROR, {"error": error})
    await run_store.mark_run_failed(agent_run_id, error, task_id=task_id)
    await emit(
        EventType.RUN_COMPLETED,
        {"status": RunStatus.FAILED.value},
    )


async def _prepare_retry(
    task_id: str | None,
    agent_run_id: str,
    attempt: int,
    error: str,
) -> None:
    """Keep accepted work non-terminal while Celery owns another attempt."""
    if task_id is None:
        return
    await run_store.mark_task_queued_for_retry(
        task_id,
        agent_run_id,
        attempt=attempt,
        error=error,
    )


@shared_task(
    bind=True,
    name="app.tasks.agent_tasks.run_agent_task",
    acks_late=True,
    **RETRY_KWARGS,
)
def run_agent_task(
    self,
    agent_run_id: str,
    conversation_id: str,
    trace_id: str,
    user_message: str,
    task_id: str | None = None,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    run_context: dict[str, Any] | None = None,
    marketplace_viewer_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """worker 入口任务:运行一次 Agent 编排。

    成功返回 orchestrator 的结果字典;失败先发布 ERROR 事件并置 run
    为 FAILED,然后在未超过最大重试次数时重试,耗尽后吞掉异常返回错误
    摘要(避免 Celery 反复堆栈污染日志)。
    """
    set_trace_id(trace_id)
    log_with_fields(
        logger,
        logging.INFO,
        "run_agent_task_started",
        agent_run_id=agent_run_id,
        attempt=self.request.retries,
    )
    try:
        return run_coro(
            _execute(
                agent_run_id,
                conversation_id,
                trace_id,
                user_message,
                task_id=task_id,
                attempt=self.request.retries,
                user_id=user_id,
                metadata=metadata or {},
                run_context=run_context or {},
                marketplace_viewer_context=marketplace_viewer_context,
            )
        )
    except ProviderRateLimitError as exc:
        if self.request.retries < self.max_retries:
            countdown = max(1, int((exc.retry_after_ms or 1000) / 1000))
            run_coro(
                _prepare_retry(
                    task_id,
                    agent_run_id,
                    self.request.retries + 1,
                    exc.reason,
                )
            )
            raise self.retry(exc=exc, countdown=countdown)
        error = f"{type(exc).__name__}: {exc.reason}"
        try:
            run_coro(
                _publish_error(
                    agent_run_id,
                    trace_id,
                    error,
                    task_id=task_id,
                )
            )
        except Exception:
            pass
        return {"status": "FAILED", "error": error}
    except Exception as exc:  # noqa: BLE001 顶层兜底:发事件 + 失败状态 + 重试
        error = redact_runtime_error(f"{type(exc).__name__}: {exc}")
        log_with_fields(
            logger,
            logging.ERROR,
            "run_agent_task_failed",
            agent_run_id=agent_run_id,
            attempt=self.request.retries,
            error=error,
        )
        if self.request.retries < self.max_retries:
            try:
                run_coro(
                    _prepare_retry(
                        task_id,
                        agent_run_id,
                        self.request.retries + 1,
                        error,
                    )
                )
            except Exception:  # noqa: BLE001 retry bookkeeping must not hide root cause
                pass
            raise self.retry(exc=exc)
        try:
            run_coro(
                _publish_error(
                    agent_run_id,
                    trace_id,
                    error,
                    task_id=task_id,
                )
            )
        except Exception:  # noqa: BLE001 错误上报本身失败时不再上抛
            pass
        return {"status": "FAILED", "error": error}


@shared_task(
    bind=True,
    name="app.tasks.agent_tasks.rag_ingest_document",
    acks_late=True,
    **RETRY_KWARGS,
)
def rag_ingest_document(self, job_id: str, document_id: str) -> dict[str, Any]:
    """worker 入口任务:摄取一份 RAG 文档。"""
    log_with_fields(
        logger,
        logging.INFO,
        "rag_ingest_document_started",
        job_id=job_id,
        document_id=document_id,
        attempt=self.request.retries,
    )
    try:
        from app.rag.service import build_ingestion_service

        chunks = run_coro(
            build_ingestion_service().ingest_document(
                job_id=job_id,
                document_id=document_id,
                final_attempt=self.request.retries >= self.max_retries,
            )
        )
        return {"status": "SUCCEEDED", "chunks": chunks}
    except Exception as exc:  # noqa: BLE001
        error = redact_runtime_error(f"{type(exc).__name__}: {exc}")
        log_with_fields(
            logger,
            logging.ERROR,
            "rag_ingest_document_failed",
            job_id=job_id,
            document_id=document_id,
            attempt=self.request.retries,
            error=error,
        )
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {"status": "FAILED", "error": error}
