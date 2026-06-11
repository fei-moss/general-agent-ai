"""API 出入参 Schema(Pydantic v2)。

定义 HTTP 接口的请求体与响应体模型,与 ORM 模型解耦,作为前后端契约。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import IntentType, MessageRole, RunStatus, TaskStatus


class ChatRequest(BaseModel):
    """提交一次对话/任务的请求体。"""

    conversation_id: str | None = None
    message: str
    stream: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatAccepted(BaseModel):
    """POST /runs 受理后的 202 响应体。"""

    conversation_id: str
    agent_run_id: str
    trace_id: str
    status: RunStatus
    stream_url: str
    ws_url: str
    route_type: str | None = None


class MessageOut(BaseModel):
    """消息出参。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    agent_run_id: str | None = None
    role: MessageRole
    content: str
    token_count: int
    created_at: datetime
    meta: dict[str, Any] = Field(default_factory=dict)


class ConversationOut(BaseModel):
    """会话出参。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str | None = None
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class ToolCallOut(BaseModel):
    """工具调用日志出参。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_run_id: str
    tool_name: str
    arguments: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    attempt: int = 0
    latency_ms: int
    status: TaskStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class AgentRunOut(BaseModel):
    """Agent 运行出参。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    trace_id: str
    status: RunStatus
    intent: IntentType | None = None
    plan: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RunStatusOut(BaseModel):
    """GET /runs/{id} 的轻量状态出参。"""

    agent_run_id: str
    status: RunStatus
    intent: IntentType | None = None
    error: str | None = None
