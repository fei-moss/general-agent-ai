from __future__ import annotations

from typing import Any

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import FunctionModel

from app.runtime.agent_factory import (
    AgentDeps,
    TOOL_MARKETPLACE_AGENT_COMPUTE,
    TOOL_MARKETPLACE_AGENT_CONTEXT,
    build_agent,
)
from app.runtime.marketplace_ai import MarketplaceViewerContext


ADDRESS = "0x17B09FC949f031dbD540D4caDE59805A08Ee5043"
VIEWER = MarketplaceViewerContext(
    user_id="marketplace:user:7",
    wallet="0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
    agent_run_id="run-tool-1",
    conversation_id="conv-tool-1",
    trace_id="trace-tool-1",
)


async def test_agent_marketplace_context_tool_ignores_context_chain_id_by_default():
    marketplace = _FakeMarketplaceAI()
    agent = build_agent(
        _tool_calling_model(
            TOOL_MARKETPLACE_AGENT_CONTEXT,
            {"reports_limit": 1, "include_raw": False},
        )
    )
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        marketplace_ai=marketplace,
        marketplace_viewer_context=VIEWER,
        run_context={
            "marketplace_agent": {
                "address": ADDRESS,
                "chain_id": 999,
            }
        },
    )

    result = await agent.run("这个 Agent 是做什么的?", deps=deps)

    assert marketplace.context_calls == [
        {
            "address": ADDRESS,
            "chain_id": None,
            "reports_limit": 1,
            "include_raw": False,
            "viewer_context": VIEWER,
        }
    ]
    assert "BTC Trend Agent" in repr(result)


async def test_agent_marketplace_compute_tool_passes_metric_queries_without_chain_id():
    marketplace = _FakeMarketplaceAI()
    agent = build_agent(
        _tool_calling_model(
            TOOL_MARKETPLACE_AGENT_COMPUTE,
            {
                "queries": [
                    {
                        "id": "q1",
                        "metric": "volume_sum",
                        "window": {"unit": "day", "value": 1},
                    }
                ]
            },
        )
    )
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        marketplace_ai=marketplace,
        marketplace_viewer_context=VIEWER,
        run_context={"agent": {"contract_address": ADDRESS, "chain_id": 999}},
    )

    result = await agent.run("24 小时交易量是多少?", deps=deps)

    assert marketplace.compute_calls == [
        {
            "address": ADDRESS,
            "chain_id": None,
            "queries": [
                {
                    "id": "q1",
                    "metric": "volume_sum",
                    "window": {"unit": "day", "value": 1},
                }
            ],
            "viewer_context": VIEWER,
        }
    ]
    assert "volume_sum" in repr(result)
    assert '"status": "ok"' in repr(result) or "'status': 'ok'" in repr(result)


async def test_agent_marketplace_tool_requires_current_agent_context():
    marketplace = _FakeMarketplaceAI()
    agent = build_agent(_tool_calling_model(TOOL_MARKETPLACE_AGENT_CONTEXT, {}))
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        marketplace_ai=marketplace,
        run_context={},
    )

    result = await agent.run("这个 Agent 的 AUM 是多少?", deps=deps)

    assert marketplace.context_calls == []
    assert "CURRENT_AGENT_ADDRESS_MISSING" in repr(result)


async def test_agent_marketplace_compute_requires_trusted_viewer_context():
    marketplace = _FakeMarketplaceAI()
    agent = build_agent(
        _tool_calling_model(
            TOOL_MARKETPLACE_AGENT_COMPUTE,
            {"queries": [{"metric": "volume_sum"}]},
        )
    )
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        marketplace_ai=marketplace,
        run_context={"agent": {"contract_address": ADDRESS}},
    )

    result = await agent.run("过去一天的 volume_sum", deps=deps)

    assert marketplace.compute_calls == []
    assert "marketplace_viewer_context_missing" in repr(result)


def test_marketplace_tool_schemas_do_not_accept_agent_address_or_wallet():
    agent = build_agent(_tool_calling_model(TOOL_MARKETPLACE_AGENT_CONTEXT, {}))
    schemas = {
        tool.name: tool.function_schema.json_schema
        for tool in agent._function_toolset.tools.values()
        if tool.name in {TOOL_MARKETPLACE_AGENT_CONTEXT, TOOL_MARKETPLACE_AGENT_COMPUTE}
    }

    rendered = repr(schemas).lower()
    assert "wallet" not in rendered
    assert "agent_address" not in rendered
    assert "contract_address" not in rendered


async def test_compute_query_cannot_override_server_agent_or_viewer_identity():
    marketplace = _FakeMarketplaceAI()
    agent = build_agent(
        _tool_calling_model(
            TOOL_MARKETPLACE_AGENT_COMPUTE,
            {
                "queries": [
                    {
                        "metric": "volume_sum",
                        "wallet": "0x1111111111111111111111111111111111111111",
                        "agent_address": "0x2222222222222222222222222222222222222222",
                    }
                ]
            },
        )
    )
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        marketplace_ai=marketplace,
        marketplace_viewer_context=VIEWER,
        run_context={"agent": {"contract_address": ADDRESS}},
    )

    await agent.run("计算 volume_sum", deps=deps)

    assert marketplace.compute_calls == [
        {
            "address": ADDRESS,
            "chain_id": None,
            "queries": [{"metric": "volume_sum"}],
            "viewer_context": VIEWER,
        }
    ]


async def test_agent_marketplace_tool_permission_denial_blocks_client_call():
    marketplace = _FakeMarketplaceAI()
    agent = build_agent(_tool_calling_model(TOOL_MARKETPLACE_AGENT_CONTEXT, {}))
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        marketplace_ai=marketplace,
        run_context={
            "marketplace_agent": {"address": ADDRESS},
            "tool_permissions": {"denied": [TOOL_MARKETPLACE_AGENT_CONTEXT]},
        },
    )

    result = await agent.run("这个 Agent 是做什么的?", deps=deps)

    assert marketplace.context_calls == []
    assert "TOOL_BLOCKED_BY_CONTEXT" in repr(result)


async def test_agent_marketplace_context_tool_budget_limits_external_calls():
    marketplace = _FakeMarketplaceAI()
    agent = build_agent(
        _repeated_tool_calling_model(
            TOOL_MARKETPLACE_AGENT_CONTEXT,
            {"reports_limit": 1, "include_raw": False},
            repeat=2,
        )
    )
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        marketplace_ai=marketplace,
        marketplace_viewer_context=VIEWER,
        run_context={"agent": {"contract_address": ADDRESS}},
    )

    result = await agent.run("连续查询两次 Agent 上下文", deps=deps)

    assert len(marketplace.context_calls) == 1
    assert "BTC Trend Agent" in repr(result)


async def test_agent_marketplace_compute_tool_budget_limits_external_calls():
    marketplace = _FakeMarketplaceAI()
    args = {
        "queries": [
            {
                "id": "q1",
                "metric": "volume_sum",
                "window": {"unit": "day", "value": 1},
            }
        ]
    }
    agent = build_agent(
        _repeated_tool_calling_model(TOOL_MARKETPLACE_AGENT_COMPUTE, args, repeat=2)
    )
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        marketplace_ai=marketplace,
        marketplace_viewer_context=VIEWER,
        run_context={"agent": {"contract_address": ADDRESS}},
    )

    result = await agent.run("连续计算两次交易量", deps=deps)

    assert len(marketplace.compute_calls) == 1
    assert "volume_sum" in repr(result)


async def test_agent_marketplace_compute_merges_same_response_duplicate_tool_calls():
    marketplace = _FakeMarketplaceAI()
    q1 = {
        "id": "q1",
        "metric": "volume_sum",
        "window": {"unit": "day", "value": 1},
    }
    q2 = {
        "id": "q2",
        "metric": "aum_latest",
        "window": {"unit": "day", "value": 1},
    }
    agent = build_agent(
        _multi_tool_calling_model(
            [
                ToolCallPart(
                    tool_name=TOOL_MARKETPLACE_AGENT_COMPUTE,
                    args={"queries": [q1]},
                ),
                ToolCallPart(
                    tool_name=TOOL_MARKETPLACE_AGENT_COMPUTE,
                    args={"queries": [q2]},
                ),
            ]
        )
    )
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        marketplace_ai=marketplace,
        marketplace_viewer_context=VIEWER,
        run_context={"agent": {"contract_address": ADDRESS}},
    )

    result = await agent.run("同时计算 24 小时交易量和最新 AUM", deps=deps)

    assert len(marketplace.compute_calls) == 1
    assert marketplace.compute_calls[0]["queries"] == [q1, q2]
    assert "volume_sum" in repr(result)


class _NoopRetriever:
    async def retrieve(self, query: str, top_k: int):
        return []


class _NoopToolRouter:
    async def route(self, query: str, tool_name: str | None = None, **kwargs):
        return {"tool_name": tool_name, "result": {}, "status": "DONE"}


class _FakeMarketplaceAI:
    def __init__(self) -> None:
        self.context_calls: list[dict[str, Any]] = []
        self.compute_calls: list[dict[str, Any]] = []

    async def get_agent_context(
        self,
        address: str,
        *,
        chain_id: int | None = None,
        reports_limit: int = 5,
        include_raw: bool = False,
        viewer_context: MarketplaceViewerContext | None = None,
    ) -> dict[str, Any]:
        self.context_calls.append(
            {
                "address": address,
                "chain_id": chain_id,
                "reports_limit": reports_limit,
                "include_raw": include_raw,
                "viewer_context": viewer_context,
            }
        )
        return {
            "ok": True,
            "source": "marketplace_ai",
            "data": {
                "agent": {"name": "BTC Trend Agent"},
                "metrics": {"volume_24h_usd": "0"},
                "recent_reports": [],
            },
        }

    async def compute_agent_metrics(
        self,
        address: str,
        queries: list[dict[str, Any]],
        *,
        chain_id: int | None = None,
        viewer_context: MarketplaceViewerContext | None = None,
    ) -> dict[str, Any]:
        self.compute_calls.append(
            {
                "address": address,
                "chain_id": chain_id,
                "queries": queries,
                "viewer_context": viewer_context,
            }
        )
        return {
            "ok": True,
            "source": "marketplace_ai",
            "data": {
                "agent_id": 1051,
                "results": [
                    {
                        "id": "q1",
                        "metric": "volume_sum",
                        "available": True,
                        "status": "ok",
                        "value": "0",
                        "unit": "usd",
                    }
                ],
            },
        }


def _tool_calling_model(tool_name: str, args: dict[str, Any]) -> FunctionModel:
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
                        return ModelResponse(
                            parts=[TextPart(content=repr(part.content))]
                        )
        return ModelResponse(parts=[TextPart(content="done")])

    return FunctionModel(function=function)


def _multi_tool_calling_model(tool_calls: list[ToolCallPart]) -> FunctionModel:
    calls = 0

    def function(messages, _info):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ModelResponse(parts=tool_calls)
        for message in messages:
            if isinstance(message, ModelRequest):
                for part in message.parts:
                    if isinstance(part, ToolReturnPart):
                        return ModelResponse(
                            parts=[TextPart(content=repr(part.content))]
                        )
        return ModelResponse(parts=[TextPart(content="done")])

    return FunctionModel(function=function)


def _repeated_tool_calling_model(
    tool_name: str, args: dict[str, Any], *, repeat: int
) -> FunctionModel:
    def function(messages, info):
        tool_results = []
        for message in messages:
            if isinstance(message, ModelRequest):
                for part in message.parts:
                    if isinstance(part, ToolReturnPart):
                        tool_results.append(part.content)
        visible_tools = {tool.name for tool in info.function_tools}
        if len(tool_results) < repeat and tool_name in visible_tools:
            return ModelResponse(parts=[ToolCallPart(tool_name=tool_name, args=args)])
        return ModelResponse(parts=[TextPart(content=repr(tool_results))])

    return FunctionModel(function=function)
