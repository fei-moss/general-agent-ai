"""流式事件契约。

定义 Agent 执行过程中通过 Redis Pub/Sub 广播、并经 SSE/WebSocket 推送
给客户端的事件模型 AgentEvent。所有事件按 seq 严格递增,支持断线回放。
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.core.ids import new_event_id


class EventType(str, Enum):
    """事件类型,覆盖一次 Agent 运行的全部阶段。"""

    RUN_STARTED = "RUN_STARTED"
    PLANNING_STARTED = "PLANNING_STARTED"
    INTENT_RESOLVED = "INTENT_RESOLVED"
    RETRIEVAL_STARTED = "RETRIEVAL_STARTED"
    RETRIEVAL_FINISHED = "RETRIEVAL_FINISHED"
    TOOL_CALL_STARTED = "TOOL_CALL_STARTED"
    TOOL_CALL_FINISHED = "TOOL_CALL_FINISHED"
    LLM_GENERATING = "LLM_GENERATING"
    TOKEN = "TOKEN"
    RESULT_COMPOSED = "RESULT_COMPOSED"
    RUN_COMPLETED = "RUN_COMPLETED"
    ERROR = "ERROR"


class AgentEvent(BaseModel):
    """单条流式事件。

    字段:
        event_id: 事件唯一 ID(evt_ 前缀)。
        agent_run_id: 所属运行 ID。
        trace_id: 链路追踪 ID。
        type: 事件类型。
        seq: 同一运行内单调递增序号,用于排序与回放去重。
        ts: 事件产生的 unix 时间戳(秒,float)。
        data: 事件载荷,结构随 type 而定。
    """

    event_id: str = Field(default_factory=new_event_id)
    agent_run_id: str
    trace_id: str
    type: EventType
    seq: int
    ts: float = Field(default_factory=time.time)
    data: dict[str, Any] = Field(default_factory=dict)

    def to_json(self) -> str:
        """序列化为 JSON 字符串(用于写入 Pub/Sub)。"""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str) -> "AgentEvent":
        """从 JSON 字符串反序列化(从 Pub/Sub 读取)。"""
        return cls.model_validate_json(raw)

    def to_sse(self) -> dict[str, str]:
        """转为 sse-starlette ServerSentEvent 所需的字段字典。

        返回包含 event/id/data 的字典,data 为事件 JSON 字符串。
        """
        return {
            "event": self.type.value,
            "id": str(self.seq),
            "data": self.to_json(),
        }
