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
    _knowledge_query_for_context,
    _is_correctable_compute_failure,
    _missing_approved_mechanism_facts,
    _safe_ballot_redeem_vote_unknown,
    _unsupported_dynamic_claims,
    _violation_feedback,
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


def test_ballot_output_guard_rejects_absence_inference_and_wrong_mechanism():
    context = {
        "data": {
            "agent": {"agent_type": "ballot"},
            "redemption_policy": {
                "available": False,
                "status": "unsupported",
            },
            "fee_schedule": {"available": False, "status": "unsupported"},
        }
    }

    output = (
        "This Agent does not have a fixed APY configured and no governance rewards "
        "are provided. The default share-weighted model applies. Yield is reflected "
        "in exchangeRate appreciation. No one can transfer or freeze contract-held "
        "principal without your signature."
    )

    violations = _unsupported_dynamic_claims(output, context)

    assert "ballot_missing_value_as_absent" in violations
    assert "ballot_default_voting_rule" in violations
    assert "ballot_exchange_rate_yield" in violations
    assert "ballot_contract_signature_overclaim" in violations


def test_ballot_output_guard_accepts_missing_data_and_contract_boundary():
    context = {"data": {"agent": {"agent_type": "ballot"}}}
    output = (
        "The current Agent context does not provide its fixed APY, voting-reward "
        "configuration, or exact voting formula. Stable Ballot mechanics come from "
        "the platform knowledge base. Wallet-held assets require your signature; "
        "after Mint, deposited principal follows the contract and executor permissions."
    )

    assert _unsupported_dynamic_claims(output, context) == []


def test_ballot_knowledge_query_is_qualified_by_typed_agent_context():
    context = {"data": {"agent": {"agent_type": "ballot"}}}

    assert _knowledge_query_for_context("How do rewards work?", context) == (
        "Governance Ballot stable platform mechanism for the current Agent: "
        "How do rewards work?"
    )
    assert _knowledge_query_for_context("How do fees work?", None) == (
        "How do fees work?"
    )


def test_ballot_retry_feedback_names_the_required_missing_data_wording():
    assert "not provided" in _violation_feedback("ballot_missing_value_as_absent")
    assert "未提供" in _violation_feedback("ballot_missing_value_as_absent")


def test_ballot_output_guard_rejects_redeem_vote_answer_when_rule_is_missing():
    context = {
        "data": {
            "agent": {"agent_type": "ballot"},
            "ballot_governance": {
                "redeem_during_vote_rule": {
                    "availability": "not_provided",
                    "value": None,
                }
            },
        }
    }

    assert "ballot_redeem_vote_rule_invented" in _unsupported_dynamic_claims(
        "Redeeming after the snapshot does not affect the vote you cast.", context
    )
    assert "ballot_redeem_vote_rule_invented" in _unsupported_dynamic_claims(
        "赎回不会影响已经投出的票，这一票仍然有效。", context
    )
    assert "ballot_redeem_vote_rule_invented" in _unsupported_dynamic_claims(
        "快照后的 Redeem 不影响已记录的投票权重，你的票仍然算数。", context
    )


def test_ballot_output_guard_rejects_proportional_vote_assertion_when_rule_is_missing():
    context = {
        "data": {
            "agent": {"agent_type": "ballot"},
            "ballot_governance": {
                "voting_power_rule": {
                    "availability": "not_provided",
                    "value": None,
                }
            },
        }
    }

    assert "ballot_proportional_voting_rule_invented" in _unsupported_dynamic_claims(
        "Voting power is proportional to your shares.", context
    )
    assert "ballot_proportional_voting_rule_invented" not in _unsupported_dynamic_claims(
        "If the rule is share-proportional, a large holder could have influence; "
        "the current voting power rule is not provided.",
        context,
    )


def test_ballot_output_guard_allows_snapshot_mechanism_without_redeem_claim():
    context = {
        "data": {
            "agent": {"agent_type": "ballot"},
            "ballot_governance": {
                "redeem_during_vote_rule": {
                    "availability": "not_provided",
                    "value": None,
                }
            },
        }
    }

    output = (
        "A snapshot fixes eligibility and voting weight for that proposal. "
        "The current Agent does not provide its redeem-during-vote rule."
    )
    assert "ballot_redeem_vote_rule_invented" not in _unsupported_dynamic_claims(
        output, context
    )


def test_ballot_redeem_vote_safe_answer_is_bilingual_and_does_not_reassert_outcome():
    english = _safe_ballot_redeem_vote_unknown(
        "If I redeem during a vote, does my vote still count?"
    )
    chinese = _safe_ballot_redeem_vote_unknown("投票期间我赎回了，我的票还算吗？")

    assert "redeem_during_vote_rule" in english
    assert "not provided" in english
    assert "cannot determine" in english
    assert "redeem_during_vote_rule" in chinese
    assert "未提供" in chinese
    assert "无法确认" in chinese


def test_ballot_fixed_apy_change_answer_requires_complete_stable_mechanism():
    assert _missing_approved_mechanism_facts(
        "Can the fixed APY change later?",
        "The current Agent does not provide its fixed APY.",
        agent_type="ballot",
    ) == [
        "fixed APY is set and disclosed at launch/固定收益率在发起时设定并公开",
        "fixed APY is enforced by contract/固定收益率由合约执行",
        "fixed APY cannot be changed after the fact/固定收益率不能事后更改",
    ]
    assert _missing_approved_mechanism_facts(
        "固定收益率以后会变吗？",
        "固定收益率在发起时设定并公开，由合约执行，不能事后更改。",
        agent_type="ballot",
    ) == []


def test_ballot_fixed_apy_accrual_requires_basis_and_enforcement():
    missing = _missing_approved_mechanism_facts(
        "How does the fixed APY accrue?",
        "Fixed yield accrues while you hold shares.",
        agent_type="ballot",
    )

    assert "share size/份额规模" in missing
    assert "holding duration/持有时长" in missing
    assert "annualized rate/年化" in missing
    assert "rate set and disclosed at launch/费率在发起时设定并公开" in missing
    assert "contract enforcement/合约执行" in missing
    assert "accrual display location availability/累积展示位置可用性" in missing


def test_ballot_airdrop_claim_requires_complete_redemption_bundle():
    missing = _missing_approved_mechanism_facts(
        "When and how do I claim airdrops?",
        "Airdrops accrue while you hold and are claimed at Redeem.",
        agent_type="ballot",
    )

    assert "principal returned at Redeem/赎回本金" in missing
    assert "fixed yield delivered at Redeem/赎回固定收益" in missing


def test_ballot_reward_sustainability_requires_contract_boundary():
    missing = _missing_approved_mechanism_facts(
        "Where do the rewards come from? Are they sustainable?",
        "The current reward source is not provided, so sustainability is unknown.",
        agent_type="ballot",
    )

    assert "contract-governed reward rules/奖励规则由合约执行" in missing


def test_ballot_exit_answer_requires_complete_redemption_bundle():
    missing = _missing_approved_mechanism_facts(
        "Can I exit anytime? Do I lose accrued rewards?",
        "Redemption is unsupported for the current Agent; airdrops are not provided.",
        agent_type="ballot",
    )

    assert "principal returned at Redeem/赎回本金" in missing
    assert "fixed yield delivered at Redeem/赎回固定收益" in missing


def test_ballot_vote_how_to_requires_cost_availability():
    missing = _missing_approved_mechanism_facts(
        "How do I vote? Can I change my vote?",
        "Choose on the proposal page, sign, and check the vote change rule.",
        agent_type="ballot",
    )

    assert "vote cost or gas availability/投票费用或 Gas 可用性" in missing


def test_ballot_payout_token_answer_requires_redeem_and_display_availability():
    missing = _missing_approved_mechanism_facts(
        "What tokens are the yield and airdrops paid in?",
        "Yield denomination and airdrop token are not provided.",
        agent_type="ballot",
    )

    assert "claim at Redeem/在 Redeem 时领取" in missing
    assert "accrual display location availability/累积展示位置可用性" in missing


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
                        "mechanism. It seems to be a test agent. The fee schedule "
                        "includes only this fee. 管理费不会因亏损而豁免，领取前需要进行结算。"
                        "锁定等待 → 结算 → Claim。"
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
    assert "seems to be a test agent" in retry_feedback[0]
    assert "fee schedule includes only" in retry_feedback[0]
    assert "不会因亏损而豁免" in retry_feedback[0]
    assert "领取前需要进行结算" in retry_feedback[0]
    assert "锁定等待 → 结算" in retry_feedback[0]
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
    retry_attempts = 0
    calls = 0

    def function(messages, _info):
        nonlocal calls, retry_attempts
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
                    retry_attempts += 1
                    if retry_attempts == 1:
                        return ModelResponse(
                            parts=[
                                TextPart(
                                    content=(
                                        "You receive a proportional share in your wallet "
                                        "and the executor uses it for the strategy."
                                    )
                                )
                            ]
                        )
                    return ModelResponse(
                        parts=[
                            TextPart(
                                content=(
                                    "You receive a proportional on-chain share in your "
                                    "wallet. Pooled assets enter the contract for the "
                                    "executor's strategy, and the creator cannot freely "
                                    "dispose of pooled principal."
                                )
                            )
                        ]
                    )
        return ModelResponse(
            parts=[
                TextPart(
                    content=(
                        "After minting there is a lock. The search didn't return a "
                        "direct answer, so let me search again. Mint 后需经过锁定期。"
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

    result = await agent.run("What happens when I mint a share?", deps=deps)

    assert calls == 4
    assert retry_attempts == 2
    assert "after minting there is a lock" in retry_feedback[0]
    assert "mint 后需经过" in retry_feedback[0]
    assert "the search didn't return" in retry_feedback[0]
    assert "let me search" in retry_feedback[0]
    assert "wallet" in retry_feedback[0]
    assert "creator cannot freely dispose" in retry_feedback[0]
    assert "proportional on-chain share" in result.output


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
            return ModelResponse(
                parts=[
                    TextPart(
                        content=(
                            "You receive a proportional share in your wallet. Pooled "
                            "assets enter the contract for the executor's strategy, and "
                            "the creator cannot freely dispose of pooled principal."
                        )
                    )
                ]
            )
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
    assert "creator cannot freely dispose" in result.output


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
