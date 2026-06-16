"""抽象接口契约。

使用 typing.Protocol 定义可插拔组件的接口:LLMProvider / Embedder /
VectorStore / Tool / EventBus / Repository。具体实现位于各自模块,
运行时通过工厂按配置选择。所有方法均为异步以契合异步执行平台。
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Protocol, runtime_checkable

from app.core.events import AgentEvent


@runtime_checkable
class LLMProvider(Protocol):
    """大模型 Provider 接口。支持流式与一次性补全。"""

    @property
    def name(self) -> str:
        """Provider 名称(如 mock / openai / anthropic)。"""
        ...

    async def stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[str]:
        """流式生成,逐 token(或文本片段)产出。"""
        ...

    async def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """一次性返回完整生成文本。"""
        ...


@runtime_checkable
class Embedder(Protocol):
    """文本向量化接口。"""

    @property
    def dim(self) -> int:
        """输出向量维度。"""
        ...

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """将文本列表编码为向量列表(顺序对应)。"""
        ...


@runtime_checkable
class VectorStore(Protocol):
    """向量存储与检索接口。"""

    async def add(self, docs: list[dict[str, Any]]) -> None:
        """新增文档。每个 doc 至少含 id/text/vector 字段。"""
        ...

    async def search(
        self, query_vec: list[float], top_k: int, **filters: Any
    ) -> list[tuple[dict[str, Any], float]]:
        """按相似度返回 (doc, score) 列表,score 越大越相似。"""
        ...


@runtime_checkable
class Tool(Protocol):
    """可被 Agent 调用的工具接口。"""

    @property
    def name(self) -> str:
        """工具唯一名称。"""
        ...

    @property
    def description(self) -> str:
        """工具用途的自然语言描述(供 LLM 选择)。"""
        ...

    @property
    def parameters(self) -> dict[str, Any]:
        """参数的 JSON Schema。"""
        ...

    async def run(self, args: dict[str, Any]) -> dict[str, Any]:
        """执行工具并返回结构化结果。"""
        ...


@runtime_checkable
class EventBus(Protocol):
    """事件总线接口,基于 channel(通常为 run:{agent_run_id})收发事件。"""

    async def publish(self, channel: str, event: AgentEvent) -> None:
        """向 channel 发布一条事件。"""
        ...

    def subscribe(self, channel: str) -> AsyncIterator[AgentEvent]:
        """订阅 channel,异步迭代产出事件。"""
        ...


@runtime_checkable
class Repository(Protocol):
    """数据访问通用接口(可选,供需要泛型仓储的实现使用)。"""

    async def get(self, entity_id: str) -> Any | None:
        """按主键获取实体,不存在返回 None。"""
        ...

    async def add(self, entity: Any) -> Any:
        """新增实体并返回(可能带回填字段)。"""
        ...

    async def update(self, entity: Any) -> Any:
        """更新实体并返回更新后的副本。"""
        ...

    async def delete(self, entity_id: str) -> None:
        """按主键删除实体。"""
        ...
