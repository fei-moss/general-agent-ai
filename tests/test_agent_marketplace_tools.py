from __future__ import annotations

from typing import Any

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import FunctionModel

from app.runtime.agent_factory import (
    AgentDeps,
    TOOL_MARKETPLACE_AGENT_COMPUTE,
    TOOL_MARKETPLACE_AGENT_CONTEXT,
    _is_correctable_compute_failure,
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


async def test_agent_marketplace_context_tool_exposes_typed_dynamic_config():
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
        run_context={"agent": {"contract_address": ADDRESS}},
    )

    result = await agent.run("How do I exit and what fees apply?", deps=deps)

    rendered = repr(result)
    assert "lock_period_seconds" in rendered
    assert "10000" in rendered
    assert "claim_required" in rendered
    assert "management_fee" in rendered
    assert "rate_bps" in rendered


async def test_current_agent_output_retries_unsupported_dynamic_claim_once():
    marketplace = _FakeMarketplaceAI()
    retry_feedback: list[str] = []
    calls = 0

    def function(messages, _info):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name=TOOL_MARKETPLACE_AGENT_CONTEXT,
                        args={"reports_limit": 1, "include_raw": False},
                    )
                ]
            )
        for message in messages:
            if not isinstance(message, ModelRequest):
                continue
            for part in message.parts:
                if isinstance(part, RetryPromptPart):
                    retry_feedback.append(str(part.content))
                    return ModelResponse(
                        parts=[
                            TextPart(
                                content=(
                                    "Management Fee: 1%. The source does not return "
                                    "fee cadence, collection mechanics, or other fee types."
                                )
                            )
                        ]
                    )
        return ModelResponse(
            parts=[
                TextPart(
                    content=(
                        "Management Fee: 1% per annum. This is the only fee "
                        "currently configured. Settlement must occur before you "
                        "can claim because it closes positions. The fee is based "
                        "on assets under management, is unrelated to profit or "
                        "loss, and is not waived for losses. There is no insurance "
                        "mechanism or loss-absorbing party and no generic stop-loss "
                        "mechanism."
                    )
                )
            ]
        )

    agent = build_agent(FunctionModel(function=function))
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        marketplace_ai=marketplace,
        marketplace_viewer_context=VIEWER,
        run_context={
            "agent": {"contract_address": ADDRESS},
            "turn_policy": {
                "intent": "current_agent_question",
                "tool_use": "marketplace_context_first",
            },
        },
    )

    result = await agent.run("What fees do you charge?", deps=deps)

    assert calls == 3
    assert len(marketplace.context_calls) == 1
    assert retry_feedback
    assert "per annum" in retry_feedback[0]
    assert "only fee currently configured" in retry_feedback[0]
    assert "settlement must occur before you can claim" in retry_feedback[0]
    assert "closes positions" in retry_feedback[0]
    assert "based on assets under management" in retry_feedback[0]
    assert "unrelated to profit or loss" in retry_feedback[0]
    assert "not waived for losses" in retry_feedback[0]
    assert "no insurance mechanism" in retry_feedback[0]
    assert "loss-absorbing party" in retry_feedback[0]
    assert "no generic stop-loss mechanism" in retry_feedback[0]
    assert result.output == (
        "Management Fee: 1%. The source does not return fee cadence, "
        "collection mechanics, or other fee types."
    )
    assert "Validation feedback" not in result.output


async def test_dynamic_claim_validator_is_inactive_without_typed_context_result():
    calls = 0

    def function(_messages, _info):
        nonlocal calls
        calls += 1
        return ModelResponse(
            parts=[TextPart(content="This is the only fee currently configured.")]
        )

    agent = build_agent(FunctionModel(function=function))
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        run_context={"turn_policy": {"intent": "identity_introduction"}},
    )

    result = await agent.run("Who are you?", deps=deps)

    assert calls == 1
    assert result.output == "This is the only fee currently configured."


async def test_current_agent_output_retries_incomplete_search_and_mint_lock_claims():
    marketplace = _FakeMarketplaceAI()
    retry_feedback: list[str] = []
    calls = 0

    def function(messages, _info):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name=TOOL_MARKETPLACE_AGENT_CONTEXT,
                        args={"reports_limit": 1, "include_raw": False},
                    )
                ]
            )
        for message in messages:
            if not isinstance(message, ModelRequest):
                continue
            for part in message.parts:
                if isinstance(part, RetryPromptPart):
                    retry_feedback.append(str(part.content))
                    return ModelResponse(
                        parts=[TextPart(content="The available evidence does not say.")]
                    )
        return ModelResponse(
            parts=[
                TextPart(
                    content=(
                        "After minting there is a lock. The search didn't return a "
                        "direct answer, so let me search again."
                    )
                )
            ]
        )

    agent = build_agent(FunctionModel(function=function))
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        marketplace_ai=marketplace,
        run_context={
            "agent": {"contract_address": ADDRESS},
            "turn_policy": {
                "intent": "current_agent_question",
                "tool_use": "marketplace_context_first",
            },
        },
    )

    result = await agent.run("What happens when I mint?", deps=deps)

    assert calls == 3
    assert "after minting there is a lock" in retry_feedback[0]
    assert "the search didn't return" in retry_feedback[0]
    assert "let me search" in retry_feedback[0]
    assert result.output == "The available evidence does not say."


async def test_current_agent_context_is_forced_when_model_answers_without_tool():
    marketplace = _FakeMarketplaceAI()

    def function(messages, _info):
        returned_tools = {
            part.tool_name
            for message in messages
            if isinstance(message, ModelRequest)
            for part in message.parts
            if isinstance(part, ToolReturnPart)
        }
        if TOOL_MARKETPLACE_AGENT_CONTEXT in returned_tools:
            return ModelResponse(parts=[TextPart(content="Current Agent context used.")])
        return ModelResponse(parts=[TextPart(content="I am the assistant, not the Agent.")])

    agent = build_agent(FunctionModel(function=function))
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        marketplace_ai=marketplace,
        run_context={
            "agent": {"contract_address": ADDRESS},
            "turn_policy": {
                "intent": "current_agent_question",
                "tool_use": "marketplace_context_first",
            },
        },
    )

    result = await agent.run("What are you holding?", deps=deps)

    assert len(marketplace.context_calls) == 1
    assert result.output == "Current Agent context used."


async def test_required_platform_knowledge_is_forced_after_current_agent_context():
    marketplace = _FakeMarketplaceAI()

    class _RecordingRetriever:
        def __init__(self) -> None:
            self.queries: list[str] = []

        async def retrieve(self, query: str, _top_k: int):
            self.queries.append(query)
            return [{"text": "Approved platform mechanism."}]

    retriever = _RecordingRetriever()

    def function(messages, _info):
        returned_tools = {
            part.tool_name
            for message in messages
            if isinstance(message, ModelRequest)
            for part in message.parts
            if isinstance(part, ToolReturnPart)
        }
        if {
            TOOL_MARKETPLACE_AGENT_CONTEXT,
            "search_knowledge",
        }.issubset(returned_tools):
            return ModelResponse(parts=[TextPart(content="Approved mechanism used.")])
        return ModelResponse(parts=[TextPart(content="Answered without required evidence.")])

    agent = build_agent(FunctionModel(function=function))
    deps = AgentDeps(
        retriever=retriever,
        tool_router=_NoopToolRouter(),
        marketplace_ai=marketplace,
        run_context={
            "agent": {"contract_address": ADDRESS},
            "turn_policy": {
                "intent": "current_agent_question",
                "tool_use": "marketplace_context_first",
                "knowledge_required": True,
            },
        },
    )

    result = await agent.run("What happens when I mint your share?", deps=deps)

    assert len(marketplace.context_calls) == 1
    assert retriever.queries == ["What happens when I mint your share?"]
    assert result.output == "Approved mechanism used."


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
                        "window": {"unit": "hour", "value": 24},
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
                    "window": {"unit": "hour", "value": 24},
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
            {"queries": [{"metric": "user_status"}]},
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


def test_marketplace_compute_tool_schema_describes_query_contract():
    agent = build_agent(_tool_calling_model(TOOL_MARKETPLACE_AGENT_COMPUTE, {}))
    schema = agent._function_toolset.tools[
        TOOL_MARKETPLACE_AGENT_COMPUTE
    ].function_schema.json_schema

    query_schema = schema["$defs"]["MarketplaceComputeQuery"]
    query_properties = query_schema["properties"]
    assert set(query_properties) == {
        "id",
        "metric",
        "window",
        "time_range",
        "limit",
        "query",
        "include_raw",
    }
    assert query_properties["metric"]["enum"] == [
        "share_price_change",
        "volume_sum",
        "aum_change",
        "top_holder",
        "recent_reports",
        "report_search",
        "pnl",
        "user_pnl",
        "user_position",
        "user_status",
    ]
    window_schema = schema["$defs"]["MarketplaceComputeWindow"]
    assert window_schema["properties"]["unit"]["enum"] == ["hour", "day"]
    assert window_schema["properties"]["value"]["minimum"] == 1
    time_range_schema = schema["$defs"]["MarketplaceComputeTimeRange"]
    assert set(time_range_schema["properties"]) == {"from", "to"}
    assert time_range_schema["properties"]["from"]["format"] == "date-time"
    assert schema["properties"]["queries"]["items"] != {
        "type": "object",
        "additionalProperties": True,
    }

    rendered = repr(schema).lower()
    for forbidden in (
        "agent_address",
        "contract_address",
        "wallet",
        "wallet_address",
        "user_id",
    ):
        assert forbidden not in rendered


def test_marketplace_compute_tool_description_is_self_describing():
    agent = build_agent(_tool_calling_model(TOOL_MARKETPLACE_AGENT_COMPUTE, {}))
    description = agent._function_toolset.tools[
        TOOL_MARKETPLACE_AGENT_COMPUTE
    ].description

    assert '"metric": "volume_sum"' in description
    assert '"unit": "hour", "value": 24' in description
    assert '"metric": "user_status"' in description
    assert "一次调用" in description


def test_compute_retry_only_accepts_model_correctable_failures():
    assert _is_correctable_compute_failure(
        {
            "data": {
                "results": [
                    {"status": "invalid_request", "reason": "invalid_window"}
                ]
            }
        }
    )
    assert not _is_correctable_compute_failure(
        {"status": "invalid_request", "reason": "marketplace_http_400"}
    )


async def test_compute_query_rejects_model_supplied_agent_or_viewer_identity():
    marketplace = _FakeMarketplaceAI()
    agent = build_agent(
        _tool_calling_model(
            TOOL_MARKETPLACE_AGENT_COMPUTE,
            {
                "queries": [
                    {
                        "metric": "user_status",
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

    assert marketplace.compute_calls == []


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
        "metric": "user_status",
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


async def test_agent_marketplace_compute_combines_user_status_and_volume_in_one_call():
    marketplace = _FakeMarketplaceAI()
    queries = [
        {"id": "user-status", "metric": "user_status"},
        {
            "id": "volume-24h",
            "metric": "volume_sum",
            "window": {"unit": "hour", "value": 24},
        },
    ]
    agent = build_agent(
        _tool_calling_model(
            TOOL_MARKETPLACE_AGENT_COMPUTE,
            {"queries": queries},
        )
    )
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        marketplace_ai=marketplace,
        marketplace_viewer_context=VIEWER,
        run_context={"agent": {"contract_address": ADDRESS}},
    )

    await agent.run("当前用户状态和过去 24 小时成交量", deps=deps)

    assert len(marketplace.compute_calls) == 1
    assert marketplace.compute_calls[0]["queries"] == queries


async def test_agent_marketplace_compute_allows_one_corrective_retry_only():
    marketplace = _CorrectableThenSuccessMarketplaceAI()
    first_queries = [
        {
            "id": "volume-24h",
            "metric": "volume_sum",
            "window": {"unit": "day", "value": 1},
        }
    ]
    corrected_queries = [
        {
            "id": "volume-24h",
            "metric": "volume_sum",
            "window": {"unit": "hour", "value": 24},
        }
    ]
    agent = build_agent(
        _sequenced_tool_calling_model(
            TOOL_MARKETPLACE_AGENT_COMPUTE,
            [
                {"queries": first_queries},
                {"queries": corrected_queries},
                {"queries": corrected_queries},
            ],
        )
    )
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        marketplace_ai=marketplace,
        marketplace_viewer_context=VIEWER,
        run_context={"agent": {"contract_address": ADDRESS}},
    )

    result = await agent.run("过去 24 小时成交量", deps=deps)

    assert [call["queries"] for call in marketplace.compute_calls] == [
        first_queries,
        corrected_queries,
    ]
    assert "volume_sum" in repr(result)


async def test_acceptance_flow_calls_context_then_compute_once_without_internal_narration():
    marketplace = _FakeMarketplaceAI()
    agent = build_agent(_acceptance_flow_model())
    deps = AgentDeps(
        retriever=_NoopRetriever(),
        tool_router=_NoopToolRouter(),
        marketplace_ai=marketplace,
        marketplace_viewer_context=VIEWER,
        run_context={"agent": {"contract_address": ADDRESS}},
    )

    result = await agent.run(
        "请先获取当前 Agent 的基础上下文和最近报告，再计算当前用户状态以及过去 24 小时成交量。"
        "请直接给出结果，不要描述工具调用过程。",
        deps=deps,
    )

    assert len(marketplace.context_calls) == 1
    assert len(marketplace.compute_calls) == 1
    assert marketplace.compute_calls[0]["queries"] == [
        {"id": "user-status", "metric": "user_status"},
        {
            "id": "volume-24h",
            "metric": "volume_sum",
            "window": {"unit": "hour", "value": 24},
        },
    ]
    output = result.output
    assert "基础上下文" in output
    for internal_phrase in ("格式有误", "让我修正", "再次调用", "工具参数"):
        assert internal_phrase not in output


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
                "redemption_policy": {
                    "available": True,
                    "status": "ok",
                    "lock_period_seconds": 10000,
                    "claim_required": True,
                    "settlement_required": True,
                    "source": "onchain_contract_read",
                    "reason": None,
                },
                "fee_schedule": {
                    "available": True,
                    "status": "ok",
                    "fees": [
                        {
                            "fee_type": "management_fee",
                            "rate_bps": 100,
                            "source": "onchain_contract_read",
                        }
                    ],
                    "source": "onchain_contract_read",
                    "reason": None,
                },
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


class _CorrectableThenSuccessMarketplaceAI(_FakeMarketplaceAI):
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
        if len(self.compute_calls) == 1:
            return {
                "ok": True,
                "source": "marketplace_ai",
                "data": {
                    "results": [
                        {
                            "id": "volume-24h",
                            "metric": "volume_sum",
                            "available": False,
                            "status": "invalid_request",
                            "reason": "invalid_window",
                            "message": "Provide a valid window.",
                        }
                    ]
                },
            }
        return {
            "ok": True,
            "source": "marketplace_ai",
            "data": {
                "results": [
                    {
                        "id": "volume-24h",
                        "metric": "volume_sum",
                        "available": True,
                        "status": "ok",
                        "value": "123.45",
                        "unit": "usd",
                    }
                ]
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


def _sequenced_tool_calling_model(
    tool_name: str,
    args_sequence: list[dict[str, Any]],
) -> FunctionModel:
    def function(messages, info):
        tool_results = []
        for message in messages:
            if isinstance(message, ModelRequest):
                for part in message.parts:
                    if isinstance(part, ToolReturnPart):
                        tool_results.append(part.content)
        visible_tools = {tool.name for tool in info.function_tools}
        if len(tool_results) < len(args_sequence) and tool_name in visible_tools:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name=tool_name,
                        args=args_sequence[len(tool_results)],
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content=repr(tool_results))])

    return FunctionModel(function=function)


def _acceptance_flow_model() -> FunctionModel:
    def function(messages, info):
        returned_tools = []
        for message in messages:
            if isinstance(message, ModelRequest):
                for part in message.parts:
                    if isinstance(part, ToolReturnPart):
                        returned_tools.append(part.tool_name)
        visible_tools = {tool.name for tool in info.function_tools}
        if (
            TOOL_MARKETPLACE_AGENT_CONTEXT not in returned_tools
            and TOOL_MARKETPLACE_AGENT_CONTEXT in visible_tools
        ):
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name=TOOL_MARKETPLACE_AGENT_CONTEXT,
                        args={"reports_limit": 5, "include_raw": False},
                    )
                ]
            )
        if (
            TOOL_MARKETPLACE_AGENT_COMPUTE not in returned_tools
            and TOOL_MARKETPLACE_AGENT_COMPUTE in visible_tools
        ):
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name=TOOL_MARKETPLACE_AGENT_COMPUTE,
                        args={
                            "queries": [
                                {"id": "user-status", "metric": "user_status"},
                                {
                                    "id": "volume-24h",
                                    "metric": "volume_sum",
                                    "window": {"unit": "hour", "value": 24},
                                },
                            ]
                        },
                    )
                ]
            )
        return ModelResponse(
            parts=[
                TextPart(
                    content=(
                        "基础上下文：BTC Trend Agent，最近报告为空。\n"
                        "当前用户状态：已获取。过去 24 小时成交量：0 USD。"
                    )
                )
            ]
        )

    return FunctionModel(function=function)
