"""agent_factory 单元测试:provider 选择与 mock agent 行为。"""

from __future__ import annotations

from typing import Any

from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel

from app.core.config import Settings
from app.runtime.agent_factory import (
    AgentDeps,
    build_agent,
    build_model,
)


def _settings(**overrides: Any) -> Settings:
    """构造带覆盖字段的 Settings(忽略 .env,确保测试确定性)。"""
    return Settings(_env_file=None, **overrides)


def test_build_model_returns_function_model_for_mock():
    model = build_model(_settings(llm_provider="mock"))
    assert isinstance(model, FunctionModel)


def test_build_model_unknown_provider_falls_back_to_mock():
    model = build_model(_settings(llm_provider="does-not-exist"))
    assert isinstance(model, FunctionModel)


def test_build_model_openai_uses_openai_chat_model():
    model = build_model(
        _settings(
            llm_provider="openai",
            openai_api_key="sk-test",
            openai_model="gpt-4o-mini",
        )
    )
    assert isinstance(model, OpenAIChatModel)
    assert model.model_name == "gpt-4o-mini"


def test_build_model_qwen_uses_openai_chat_model_with_qwen_model():
    model = build_model(
        _settings(
            llm_provider="qwen",
            dashscope_api_key="sk-qwen",
            qwen_model="qwen-plus",
        )
    )
    assert isinstance(model, OpenAIChatModel)
    assert model.model_name == "qwen-plus"


def test_build_model_anthropic_uses_anthropic_model():
    model = build_model(
        _settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-test",
            anthropic_model="claude-sonnet-4-6",
        )
    )
    assert isinstance(model, AnthropicModel)


def test_build_model_gemini_uses_google_model():
    model = build_model(
        _settings(
            llm_provider="gemini",
            gemini_api_key="g-test",
            gemini_model="gemini-2.5-flash",
        )
    )
    assert isinstance(model, GoogleModel)


class _SpyRetriever:
    """记录是否被检索调用的检索器替身。"""

    def __init__(self) -> None:
        self.called = False

    async def retrieve(self, query: str, top_k: int) -> list[dict[str, Any]]:
        self.called = True
        return [{"id": "d1", "text": "示例文档", "score": 0.5}]


class _NoopToolRouter:
    async def route(
        self, query: str, tool_name: str | None = None
    ) -> dict[str, Any]:
        return {"tool_name": tool_name, "result": {}, "status": "DONE"}


async def test_mock_agent_invokes_search_knowledge_tool_and_answers():
    # Arrange:mock agent 首轮应自主调用 search_knowledge 工具
    from app.runtime.agent_factory import build_mock_model

    retriever = _SpyRetriever()
    agent = build_agent(build_mock_model())
    deps = AgentDeps(
        retriever=retriever, tool_router=_NoopToolRouter(), retrieval_top_k=3
    )

    # Act
    result = await agent.run("什么是向量数据库", deps=deps)

    # Assert:检索工具被调用,且产出非空中文答案
    assert retriever.called is True
    assert isinstance(result.output, str) and result.output.strip()
