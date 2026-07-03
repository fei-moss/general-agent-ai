from __future__ import annotations

from typing import Any

from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

from app.runtime.agent_factory import AgentDeps, build_agent
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
    agent = build_agent(_tool_calling_model("web_search", {"query": "news"}))
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=router,
        run_context={"tool_permissions": {"denied": ["web_search"]}},
    )

    result = await agent.run("search news", deps=deps)

    assert "TOOL_BLOCKED_BY_CONTEXT" in repr(result)
    assert router.calls == []


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


class _NoopRetriever:
    async def retrieve(self, query: str, top_k: int):
        return []


class _NoopToolRouter:
    def __init__(self) -> None:
        self.calls = []

    async def route(self, query: str, tool_name: str | None = None, **kwargs):
        self.calls.append((query, tool_name, kwargs))
        return {"ok": True}


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
