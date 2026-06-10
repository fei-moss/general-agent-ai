"""ID 生成工具。

统一生成带语义前缀的唯一标识符,便于在日志、数据库与事件流中
肉眼区分实体类型。底层使用 uuid4 保证全局唯一性。
"""

from __future__ import annotations

import uuid

CONVERSATION_PREFIX = "conv_"
RUN_PREFIX = "run_"
TRACE_PREFIX = "trace_"
EVENT_PREFIX = "evt_"


def _new_id(prefix: str) -> str:
    """生成 `<prefix><uuid4hex>` 形式的 ID。"""
    return f"{prefix}{uuid.uuid4().hex}"


def new_conversation_id() -> str:
    """生成会话 ID,形如 conv_xxxx。"""
    return _new_id(CONVERSATION_PREFIX)


def new_run_id() -> str:
    """生成 Agent 运行 ID,形如 run_xxxx。"""
    return _new_id(RUN_PREFIX)


def new_trace_id() -> str:
    """生成链路追踪 ID,形如 trace_xxxx。"""
    return _new_id(TRACE_PREFIX)


def new_event_id() -> str:
    """生成事件 ID,形如 evt_xxxx。"""
    return _new_id(EVENT_PREFIX)
