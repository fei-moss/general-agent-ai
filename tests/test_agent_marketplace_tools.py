from __future__ import annotations

from typing import Any

from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from app.runtime.agent_factory import (
    AgentDeps,
    TOOL_MARKETPLACE_AGENT_COMPUTE,
    TOOL_MARKETPLACE_AGENT_CONTEXT,
    build_agent,
)


ADDRESS = "0x17B09FC949f031dbD540D4caDE59805A08Ee5043"


async def test_agent_marketplace_context_tool_uses_current_agent_from_run_context():
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
            "chain_id": 999,
            "reports_limit": 1,
            "include_raw": False,
        }
    ]
    assert "BTC Trend Agent" in repr(result)


async def test_agent_marketplace_compute_tool_passes_metric_queries():
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
        run_context={"agent": {"contract_address": ADDRESS}},
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
    ) -> dict[str, Any]:
        self.context_calls.append(
            {
                "address": address,
                "chain_id": chain_id,
                "reports_limit": reports_limit,
                "include_raw": include_raw,
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
    ) -> dict[str, Any]:
        self.compute_calls.append(
            {"address": address, "chain_id": chain_id, "queries": queries}
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
            from pydantic_ai.messages import ToolCallPart

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
