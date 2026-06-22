"""Celery 应用实例。

从 Settings 读取 Redis broker/result backend,配置合理的并发、超时、
重试与确认默认值,并按任务类型路由到独立队列(intent/rag/tool/llm/compose),
另设一个总的 run 队列承载编排入口任务 run_agent_task。
"""

from __future__ import annotations

import logging

from celery import Celery
from celery.signals import worker_process_init
from kombu import Queue

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# 队列名常量(与 Makefile 约定的 q.intent/q.rag/q.tool/q.llm 对齐,另加编排队列)
QUEUE_RUN = "q.run"
QUEUE_INTENT = "q.intent"
QUEUE_RAG = "q.rag"
QUEUE_TOOL = "q.tool"
QUEUE_LLM = "q.llm"
QUEUE_COMPOSE = "q.compose"

# 任务执行的软/硬超时(秒)。软超时先抛 SoftTimeLimitExceeded 供任务优雅收尾。
_TASK_SOFT_TIME_LIMIT_S = 300
_TASK_HARD_TIME_LIMIT_S = 360
# 失败重试默认值
_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE_S = 2
_RETRY_BACKOFF_MAX_S = 60

celery_app = Celery(
    "agent",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.agent_tasks"],
)

celery_app.conf.update(
    # --- 序列化 ---
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # --- 可靠性:延迟 ack,worker 崩溃时任务可被重投 ---
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # --- 并发与超时 ---
    worker_max_tasks_per_child=200,
    task_soft_time_limit=_TASK_SOFT_TIME_LIMIT_S,
    task_time_limit=_TASK_HARD_TIME_LIMIT_S,
    # --- 结果与失败处理 ---
    task_acks_on_failure_or_timeout=True,
    result_expires=3600,
    # --- 队列与路由 ---
    task_default_queue=QUEUE_RUN,
    task_queues=(
        Queue(QUEUE_RUN),
        Queue(QUEUE_INTENT),
        Queue(QUEUE_RAG),
        Queue(QUEUE_TOOL),
        Queue(QUEUE_LLM),
        Queue(QUEUE_COMPOSE),
    ),
    task_routes={
        "app.tasks.agent_tasks.run_agent_task": {"queue": QUEUE_RUN},
        "app.tasks.agent_tasks.intent_task": {"queue": QUEUE_INTENT},
        "app.tasks.agent_tasks.rag_task": {"queue": QUEUE_RAG},
        "app.tasks.agent_tasks.rag_ingest_document": {"queue": QUEUE_RAG},
        "app.tasks.agent_tasks.tool_task": {"queue": QUEUE_TOOL},
        "app.tasks.agent_tasks.llm_task": {"queue": QUEUE_LLM},
        "app.tasks.agent_tasks.compose_task": {"queue": QUEUE_COMPOSE},
    },
)

# 导出供任务模块复用的重试参数
RETRY_KWARGS = {
    "max_retries": _MAX_RETRIES,
    "default_retry_delay": _RETRY_BACKOFF_BASE_S,
    "retry_backoff": True,
    "retry_backoff_max": _RETRY_BACKOFF_MAX_S,
    "retry_jitter": True,
}


@worker_process_init.connect
def _dispose_inherited_db_pool(**_: object) -> None:
    """Reset DB pool inherited across Celery prefork worker processes."""
    try:
        from app.db import session as db_session

        db_session.engine.sync_engine.dispose(close=False)
    except Exception:  # pragma: no cover - startup best effort
        logger.exception("failed_to_dispose_inherited_db_pool")
