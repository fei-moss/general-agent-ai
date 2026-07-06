from __future__ import annotations

from typing import Any

from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

from app.runtime.agent_factory import (
    AgentDeps,
    TOOL_MARKETPLACE_AGENT_COMPUTE,
    TOOL_MARKETPLACE_AGENT_CONTEXT,
    TOOL_SEARCH_KNOWLEDGE,
    build_agent,
)
from app.runtime.chat_behavior import (
    ChatBehaviorProfile,
    DEFAULT_CHAT_BEHAVIOR_POLICY,
)
from app.runtime.tool_context import (
    build_run_context_instruction,
    mask_run_context,
    tool_allowed,
)


def test_mask_run_context_hides_locked_and_secret_values():
    masked = mask_run_context(
        {
            "match": {"id": "m1", "home": "USA"},
            "paid_block": {"locked": True, "value": "raw edge number"},
            "api": {"secret": True, "token": "raw-token"},
        }
    )

    rendered = repr(masked)
    assert "USA" in rendered
    assert "raw edge number" not in rendered
    assert "raw-token" not in rendered
    assert "[masked:locked]" in rendered
    assert "[masked:secret]" in rendered


def test_build_run_context_instruction_omits_empty_context():
    assert build_run_context_instruction({}) == ""


def test_build_run_context_instruction_includes_masked_context_only():
    instruction = build_run_context_instruction(
        mask_run_context(
            {
                "match": {"id": "m1"},
                "private": {"hidden": True, "value": "must-not-leak"},
            }
        )
    )

    assert "Server-provided runtime context" in instruction
    assert "must-not-leak" not in instruction
    assert "[masked:hidden]" in instruction


def test_tool_allowed_honors_denied_tool_permissions():
    context = {"tool_permissions": {"denied": ["web_search"]}}

    assert tool_allowed("calculator", context) is True
    assert tool_allowed("web_search", context) is False


async def test_agent_injects_masked_run_context_instruction():
    seen_messages: list[Any] = []

    def function(messages, _info):
        seen_messages.extend(messages)
        return ModelResponse(parts=[TextPart(content="ok")])

    agent = build_agent(FunctionModel(function=function))
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        run_context={
            "match": {"id": "m1"},
            "paid_block": {"locked": True, "value": "must-not-leak"},
        },
    )

    await agent.run("hello", deps=deps)

    serialized = repr(seen_messages)
    assert "Server-provided runtime context" in serialized
    assert "m1" in serialized
    assert "must-not-leak" not in serialized


async def test_agent_tool_denial_returns_structured_error_without_routing():
    router = _NoopToolRouter()
    agent = build_agent(
        _tool_calling_model("calculator", {"expression": "2+2"}),
        behavior_profile=_legacy_tools_profile(),
    )
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=router,
        run_context={"tool_permissions": {"denied": ["calculator"]}},
    )

    result = await agent.run("calculate", deps=deps)

    assert "TOOL_BLOCKED_BY_CONTEXT" in repr(result)
    assert router.calls == []


async def test_ask_this_agent_hides_generic_tools_by_default():
    seen_tool_names: list[list[str]] = []

    def function(_messages, info):
        seen_tool_names.append([tool.name for tool in info.function_tools])
        return ModelResponse(parts=[TextPart(content="ok")])

    agent = build_agent(FunctionModel(function=function))
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        run_context={},
    )

    await agent.run("Top Holders 应该怎么看?", deps=deps)

    assert seen_tool_names
    assert "web_search" not in seen_tool_names[0]
    assert "calculator" not in seen_tool_names[0]
    assert "clock" not in seen_tool_names[0]
    assert "search_knowledge" in seen_tool_names[0]
    assert "marketplace_agent_context" in seen_tool_names[0]
    assert "marketplace_agent_compute" in seen_tool_names[0]


async def test_ask_this_agent_hides_marketplace_tools_after_budget_spent():
    seen_tool_names: list[list[str]] = []

    def function(_messages, info):
        seen_tool_names.append([tool.name for tool in info.function_tools])
        return ModelResponse(parts=[TextPart(content="ok")])

    agent = build_agent(FunctionModel(function=function))
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        run_context={},
        tool_call_counts={
            TOOL_MARKETPLACE_AGENT_CONTEXT: 1,
            TOOL_MARKETPLACE_AGENT_COMPUTE: 1,
        },
    )

    await agent.run("过去一天这个 Agent 的 volume_sum 怎么算?", deps=deps)

    assert seen_tool_names
    assert TOOL_MARKETPLACE_AGENT_CONTEXT not in seen_tool_names[0]
    assert TOOL_MARKETPLACE_AGENT_COMPUTE not in seen_tool_names[0]
    assert "search_knowledge" in seen_tool_names[0]


async def test_ask_this_agent_hides_search_after_budget_spent():
    seen_tool_names: list[list[str]] = []

    def function(_messages, info):
        seen_tool_names.append([tool.name for tool in info.function_tools])
        return ModelResponse(parts=[TextPart(content="ok")])

    agent = build_agent(FunctionModel(function=function))
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        run_context={},
        tool_call_counts={
            TOOL_SEARCH_KNOWLEDGE: 1,
        },
    )

    await agent.run("过去一天这个 Agent 的 volume_sum 怎么算?", deps=deps)

    assert seen_tool_names
    assert TOOL_SEARCH_KNOWLEDGE not in seen_tool_names[0]
    assert TOOL_MARKETPLACE_AGENT_CONTEXT in seen_tool_names[0]
    assert TOOL_MARKETPLACE_AGENT_COMPUTE in seen_tool_names[0]


async def test_compute_turn_policy_exposes_only_marketplace_compute_tool():
    seen_tool_names: list[list[str]] = []

    def function(_messages, info):
        seen_tool_names.append([tool.name for tool in info.function_tools])
        return ModelResponse(parts=[TextPart(content="ok")])

    agent = build_agent(FunctionModel(function=function))
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        run_context={
            "turn_policy": {
                "intent": "marketplace_compute_metric",
                "tool_use": "marketplace_compute_only",
            }
        },
    )

    await agent.run("过去一天这个 Agent 的 volume_sum 怎么算?", deps=deps)

    assert seen_tool_names == [[TOOL_MARKETPLACE_AGENT_COMPUTE]]


async def test_agent_injects_compute_turn_policy_instruction():
    seen_messages: list[Any] = []

    def function(messages, _info):
        seen_messages.extend(messages)
        return ModelResponse(parts=[TextPart(content="ok")])

    agent = build_agent(FunctionModel(function=function))
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        run_context={
            "turn_policy": {
                "intent": "marketplace_compute_metric",
                "tool_use": "marketplace_compute_only",
            }
        },
    )

    await agent.run("过去一天这个 Agent 的 volume_sum 怎么算?", deps=deps)

    serialized = repr(seen_messages)
    assert "marketplace_agent_compute before answering" in serialized
    assert "volume_sum" in serialized


async def test_agent_disables_parallel_tool_calls_by_default():
    seen_parallel_settings: list[bool | None] = []

    def function(_messages, info):
        settings = info.model_settings or {}
        seen_parallel_settings.append(settings.get("parallel_tool_calls"))
        return ModelResponse(parts=[TextPart(content="ok")])

    agent = build_agent(FunctionModel(function=function))
    deps = AgentDeps(retriever=_NoopRetriever(), tool_router=_NoopToolRouter())

    await agent.run("这个 Agent 的 AUM 和 24 小时交易量是多少?", deps=deps)

    assert seen_parallel_settings == [False]


async def test_agent_hides_tools_when_turn_policy_disables_tool_use():
    seen_tool_names: list[list[str]] = []

    def function(_messages, info):
        seen_tool_names.append([tool.name for tool in info.function_tools])
        return ModelResponse(parts=[TextPart(content="ok")])

    agent = build_agent(FunctionModel(function=function))
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        run_context={
            "turn_policy": {
                "intent": "identity_introduction",
                "tool_use": "none",
            }
        },
    )

    await agent.run("请介绍一下你自己。", deps=deps)

    assert seen_tool_names == [[]]


async def test_agent_injects_identity_turn_policy_instruction():
    seen_messages: list[Any] = []

    def function(messages, _info):
        seen_messages.extend(messages)
        return ModelResponse(parts=[TextPart(content="ok")])

    agent = build_agent(FunctionModel(function=function))
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        run_context={
            "turn_policy": {
                "intent": "identity_introduction",
                "tool_use": "none",
            }
        },
    )

    await agent.run("请介绍一下你自己。", deps=deps)

    serialized = repr(seen_messages)
    assert "Ask this Agent information assistant" in serialized
    assert "do not introduce yourself as a generic AI assistant" in serialized
    assert "do not list internal tools" in serialized


class _NoopRetriever:
    async def retrieve(self, query: str, top_k: int):
        return []


class _NoopToolRouter:
    def __init__(self) -> None:
        self.calls = []

    async def route(self, query: str, tool_name: str | None = None, **kwargs):
        self.calls.append((query, tool_name, kwargs))
        return {"ok": True}


def _legacy_tools_profile() -> ChatBehaviorProfile:
    return ChatBehaviorProfile(
        name="legacy_tools",
        policy=DEFAULT_CHAT_BEHAVIOR_POLICY,
    )


def _tool_calling_model(tool_name: str, args: dict[str, Any]) -> FunctionModel:
    from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart

    calls = 0

    def function(messages, _info):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ModelResponse(parts=[ToolCallPart(tool_name=tool_name, args=args)])
        for message in messages:
            if isinstance(message, ModelRequest):
                for part in message.parts:
                    if isinstance(part, ToolReturnPart):
                        return ModelResponse(parts=[TextPart(content=repr(part.content))])
        return ModelResponse(parts=[TextPart(content="done")])

    return FunctionModel(function=function)
