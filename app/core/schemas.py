"""API 出入参 Schema(Pydantic v2)。

定义 HTTP 接口的请求体与响应体模型,与 ORM 模型解耦,作为前后端契约。
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.core.enums import (
    IntentType,
    KnowledgeBaseStatus,
    MessageRole,
    RAGDocumentStatus,
    RAGIngestionJobStatus,
    RunStatus,
    TaskStatus,
)


_ANCHOR_RE = re.compile(r"[^a-z0-9_.:-]+")


def _normalize_anchor_part(value: Any, *, max_length: int) -> str:
    text = _ANCHOR_RE.sub("-", str(value or "").strip().lower()).strip("-")
    if not text:
        raise ValueError("conversation_anchor 不能为空")
    if len(text) > max_length:
        raise ValueError("conversation_anchor 超过长度限制")
    return text


class ConversationAnchorIn(BaseModel):
    """Optional generic domain anchor for finding/reusing a conversation."""

    type: str = Field(min_length=1, max_length=64)
    key: str = Field(min_length=1, max_length=256)

    @field_validator("type", mode="before")
    @classmethod
    def _normalize_type(cls, value: Any) -> str:
        return _normalize_anchor_part(value, max_length=64)

    @field_validator("key", mode="before")
    @classmethod
    def _normalize_key(cls, value: Any) -> str:
        return _normalize_anchor_part(value, max_length=256)


class ChatRequest(BaseModel):
    """提交一次对话/任务的请求体。"""

    conversation_id: str | None = None
    message: str
    stream: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    proxy_payload: dict[str, Any] = Field(default_factory=dict)
    conversation_anchor: ConversationAnchorIn | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_run_context_field(cls, data: Any) -> Any:
        if isinstance(data, dict) and "run_context" in data:
            raise ValueError("run_context 已废弃,请使用 proxy_payload")
        return data

    @property
    def run_context(self) -> dict[str, Any]:
        context = dict(self.proxy_payload or {})
        metadata = self.metadata or {}
        agent_context = metadata.get("agent_context")
        existing_agent = context.get("agent")
        normalized_agent = dict(existing_agent) if isinstance(existing_agent, dict) else None
        if isinstance(agent_context, dict):
            normalized_agent = {**(normalized_agent or {}), **agent_context}
        agent_address = _metadata_agent_address(metadata, normalized_agent)

        if normalized_agent is not None:
            if agent_address:
                normalized_agent["address"] = agent_address
            context["agent"] = normalized_agent
        elif agent_address:
            context["agent"] = {"address": agent_address}

        if agent_address:
            context["agent_address"] = agent_address
        return context


def _metadata_agent_address(
    metadata: dict[str, Any],
    agent_context: dict[str, Any] | None,
) -> str | None:
    candidates = [metadata.get("current_agent_address")]
    if agent_context is not None:
        candidates.extend(
            [
                agent_context.get("agent_address"),
                agent_context.get("contract_address"),
            ]
        )
    for candidate in candidates:
        address = str(candidate or "").strip()
        if address:
            return address
    return None


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


class KnowledgeBaseCreate(BaseModel):
    """创建知识库请求。"""

    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1024)

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("name 不能为空")
        return text


class KnowledgeBaseOut(BaseModel):
    """知识库响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_user_id: str
    name: str
    description: str | None = None
    status: KnowledgeBaseStatus
    created_at: datetime
    updated_at: datetime


class RAGDocumentCreate(BaseModel):
    """导入 RAG 文档请求。Phase 1 仅接受文本/Markdown。"""

    knowledge_base_id: str = Field(min_length=1, max_length=64)
    title: str | None = Field(default=None, max_length=512)
    content: str = Field(min_length=1)
    source_type: Literal["manual", "api"] = "manual"
    source_uri: str | None = Field(default=None, max_length=2048)
    mime_type: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("content", mode="before")
    @classmethod
    def _strip_content(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("content 不能为空")
        return text


class RAGDocumentAccepted(BaseModel):
    """文档导入受理响应。"""

    document_id: str
    job_id: str
    status: RAGDocumentStatus
    replayed: bool = False


class RAGDocumentOut(BaseModel):
    """RAG 文档状态响应。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    knowledge_base_id: str
    owner_user_id: str
    title: str | None = None
    source_type: str
    source_uri: str | None = None
    mime_type: str | None = None
    status: RAGDocumentStatus
    error_message: str | None = None
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="meta",
        serialization_alias="metadata",
    )
    created_at: datetime
    updated_at: datetime


class RAGIngestionJobOut(BaseModel):
    """RAG ingestion job 状态响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    knowledge_base_id: str
    owner_user_id: str
    status: RAGIngestionJobStatus
    attempts: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class RAGQueryRequest(BaseModel):
    """RAG 查询请求。"""

    knowledge_base_id: str = Field(min_length=1, max_length=64)
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=50)
    filters: dict[str, Any] | None = None
    strict: bool = False

    @field_validator("query", mode="before")
    @classmethod
    def _strip_query(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("query 不能为空")
        return text


class CitationOut(BaseModel):
    """RAG citation 元数据。"""

    source_uri: str | None = None
    page: int | None = None
    section: str | None = None
    chunk_index: int


class KnowledgeSearchResult(BaseModel):
    """单条 RAG 检索命中。"""

    chunk_id: str
    document_id: str
    knowledge_base_id: str
    title: str | None = None
    content: str
    score: float
    citation: CitationOut
    metadata: dict[str, Any] = Field(default_factory=dict)


class RAGQueryResponse(BaseModel):
    """RAG 查询响应。"""

    chunks: list[KnowledgeSearchResult]
    degraded: bool
    reason: str | None = None
    latency_ms: int
    query_id: str | None = None
