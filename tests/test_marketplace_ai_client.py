from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from app.runtime.marketplace_ai import (
    MarketplaceAIClient,
    MarketplaceComputeQuery,
    MarketplaceComputeTimeRange,
    MarketplaceComputeWindow,
    MarketplaceViewerContext,
    annotate_ballot_context_availability,
    extract_current_ballot_agent_id,
    extract_current_agent_ref,
)


ADDRESS = "0x17B09FC949f031dbD540D4caDE59805A08Ee5043"
DEPLOYED_AT = "2026-07-17T08:12:34Z"
VIEWER = MarketplaceViewerContext(
    user_id="marketplace:user:7",
    wallet="0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
    agent_run_id="run-trusted-1",
    conversation_id="conv-trusted-1",
    trace_id="trace-trusted-1",
)


def test_ballot_context_annotation_types_available_and_missing_fields():
    result = annotate_ballot_context_availability(
        {
            "ok": True,
            "source": "marketplace_ai",
            "data": {
                "agent": {
                    "agent_type": "ballot",
                    "name": "Governance Fixture",
                    "accept_token_symbol": "GOV",
                }
            },
        }
    )

    fields = result["data"]["ballot_governance"]
    assert fields["project_name"] == {
        "availability": "available",
        "value": "Governance Fixture",
        "source": "agent.name",
    }
    assert fields["project_token"]["value"] == "GOV"
    assert fields["fixed_apy"] == {
        "availability": "not_provided",
        "value": None,
        "source": "marketplace_agent_context",
    }
    assert fields["vote_cost_note"]["availability"] == "not_provided"


def test_ballot_context_annotation_uses_returned_dynamic_governance_fields():
    result = annotate_ballot_context_availability(
        {
            "ok": True,
            "source": "marketplace_ai",
            "data": {
                "agent": {
                    "agent_type": "ballot",
                    "name": "Governance Fixture",
                    "accept_token_symbol": "GOV",
                    "proposal_creation_rule": "Holders above the threshold may propose.",
                    "voting_power_rule": "One vote per eligible wallet.",
                }
            },
        }
    )

    fields = result["data"]["ballot_governance"]
    assert fields["proposal_creation_rule"] == {
        "availability": "available",
        "value": "Holders above the threshold may propose.",
        "source": "agent.proposal_creation_rule",
    }
    assert fields["voting_power_rule"] == {
        "availability": "available",
        "value": "One vote per eligible wallet.",
        "source": "agent.voting_power_rule",
    }


def test_ballot_context_annotation_leaves_other_agent_types_unchanged():
    result = {
        "ok": True,
        "data": {"agent": {"agent_type": "hyperliquid"}},
    }

    assert annotate_ballot_context_availability(result) == result


def test_extract_current_agent_ref_ignores_context_chain_id_by_default():
    ref = extract_current_agent_ref(
        {
            "marketplace_agent": {
                "contract_address": ADDRESS,
                "chain_id": 999,
            }
        }
    )

    assert ref is not None
    assert ref.address == ADDRESS
    assert ref.chain_id is None


def test_extract_current_agent_ref_rejects_missing_or_invalid_address():
    assert extract_current_agent_ref({}) is None
    assert extract_current_agent_ref({"agent_address": "not-an-address"}) is None


def test_extract_current_ballot_agent_id_uses_server_context_only():
    assert extract_current_ballot_agent_id({"agent": {"agent_id": "#64"}}) == 64
    assert extract_current_ballot_agent_id(
        {"marketplace_agent": {"id": 1051}}
    ) == 1051
    assert extract_current_ballot_agent_id({"agent_id": "0"}) is None
    assert (
        extract_current_ballot_agent_id(
            {"agent": {"agent_id": "not-an-id"}}
        )
        is None
    )


async def test_marketplace_ai_context_builds_documented_get_request():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "agent": {
                    "id": 1051,
                    "contract_address": ADDRESS,
                    "deployed_at": DEPLOYED_AT,
                },
                "metrics": {"volume_24h_usd": "0"},
                "recent_reports": [],
                "capabilities": {"computed_metrics": ["volume_sum"]},
            },
        )

    client = MarketplaceAIClient(
        "https://market.example",
        transport=httpx.MockTransport(handler),
    )

    result = await client.get_agent_context(
        ADDRESS,
        viewer_context=VIEWER,
        chain_id=999,
        reports_limit=200,
        include_raw=True,
    )

    assert result["ok"] is True
    assert result["source"] == "marketplace_ai"
    assert result["data"]["agent"]["id"] == 1051
    assert result["data"]["agent"]["deployed_at"] == DEPLOYED_AT
    request = seen[0]
    assert request.method == "GET"
    assert request.url.path == f"/api/v1/agents/{ADDRESS}/ai-context"
    assert request.url.params["chain_id"] == "999"
    assert request.url.params["reports_limit"] == "20"
    assert request.url.params["include_raw"] == "true"
    assert request.headers["X-Marketplace-User-ID"] == VIEWER.user_id
    assert request.headers["X-Marketplace-Wallet"] == VIEWER.wallet
    assert request.headers["X-Agent-Run-ID"] == VIEWER.agent_run_id
    assert request.headers["X-Conversation-ID"] == VIEWER.conversation_id
    assert request.headers["X-Trace-ID"] == VIEWER.trace_id
    assert "Authorization" not in request.headers
    assert "Marketplace-AI-Service-Token" not in request.headers
    assert "X-Marketplace-AI-Service-Token" not in request.headers


async def test_marketplace_ballot_proposals_builds_public_read_only_get_request():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "agent_config": {"agent_id": 64},
                "items": [
                    {
                        "id": 37,
                        "title": "Current voting test",
                        "status": "open",
                        "voting_starts_at": "2026-07-28T09:48:58.282Z",
                        "voting_ends_at": "2026-08-04T09:48:58.282Z",
                        "vote_summary": {"total_vote_count": 1},
                    }
                ],
                "pagination": {"limit": 10, "offset": 0, "total": 1},
            },
        )

    client = MarketplaceAIClient(
        "https://market.example",
        transport=httpx.MockTransport(handler),
    )

    result = await client.get_ballot_proposals(64)

    assert result == {
        "ok": True,
        "source": "marketplace_ai",
        "data": {
            "items": [
                {
                    "title": "Current voting test",
                    "status": "open",
                    "voting_starts_at": "2026-07-28T09:48:58.282Z",
                    "voting_ends_at": "2026-08-04T09:48:58.282Z",
                }
            ]
        },
    }
    request = seen[0]
    assert request.method == "GET"
    assert request.url.path == "/api/v1/ballot/agents/64/proposals"
    assert dict(request.url.params) == {"limit": "10", "offset": "0"}
    assert request.headers["Accept"] == "application/json"
    assert "Authorization" not in request.headers
    assert "X-Marketplace-User-ID" not in request.headers
    assert "X-Marketplace-Wallet" not in request.headers
    assert "Marketplace-AI-Service-Token" not in request.headers
    assert "X-Marketplace-AI-Service-Token" not in request.headers


async def test_marketplace_ai_compute_builds_documented_post_request():
    seen_body: dict | None = None
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_body, seen_request
        seen_request = request
        seen_body = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "agent_id": 1051,
                "computed_at": "2026-07-03T03:05:44Z",
                "results": [
                    {
                        "id": "q1",
                        "metric": "pnl",
                        "available": False,
                        "status": "unsupported",
                        "value": None,
                        "unit": None,
                        "reason": "pnl_not_defined",
                        "message": "Agent-level PnL is not materialized yet.",
                    }
                ],
            },
        )

    client = MarketplaceAIClient(
        "https://market.example",
        transport=httpx.MockTransport(handler),
    )

    result = await client.compute_agent_metrics(
        ADDRESS,
        [
            {
                "id": "q1",
                "metric": "pnl",
                "window": {"unit": "day", "value": 7},
            }
        ],
        viewer_context=VIEWER,
    )

    assert result["ok"] is True
    assert seen_body == {
        "queries": [
            {
                "id": "q1",
                "metric": "pnl",
                "window": {"unit": "day", "value": 7},
            }
        ]
    }
    assert seen_request is not None
    assert seen_request.headers["X-Marketplace-User-ID"] == VIEWER.user_id
    assert seen_request.headers["X-Marketplace-Wallet"] == VIEWER.wallet
    assert seen_request.headers["X-Agent-Run-ID"] == VIEWER.agent_run_id
    assert seen_request.headers["X-Conversation-ID"] == VIEWER.conversation_id
    assert seen_request.headers["X-Trace-ID"] == VIEWER.trace_id
    assert "Authorization" not in seen_request.headers
    result_item = result["data"]["results"][0]
    assert result_item["available"] is False
    assert result_item["status"] == "unsupported"
    assert result_item["reason"] == "pnl_not_defined"


async def test_marketplace_ai_compute_requires_trusted_viewer_without_request():
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={})

    client = MarketplaceAIClient(
        "https://market.example",
        transport=httpx.MockTransport(handler),
    )

    result = await client.compute_agent_metrics(
        ADDRESS,
        [{"metric": "volume_sum"}],
    )

    assert calls == 0
    assert result["status"] == "unavailable"
    assert result["reason"] == "marketplace_viewer_context_missing"


@pytest.mark.parametrize(
    ("query", "message"),
    [
        (
            {"metric": "volume_sum"},
            "volume_sum requires a valid window or time_range",
        ),
        (
            {"metric": "share_price_change"},
            "share_price_change requires a valid window or time_range",
        ),
        (
            {"metric": "report_search", "query": "   "},
            "report_search requires a non-empty query",
        ),
    ],
)
def test_marketplace_compute_query_rejects_missing_metric_requirements(query, message):
    with pytest.raises(ValidationError, match=message):
        MarketplaceComputeQuery.model_validate(query)


@pytest.mark.parametrize(
    "window",
    [
        {"unit": "minute", "value": 24},
        {"unit": "hour", "value": 0},
        {"unit": "day", "value": -1},
    ],
)
def test_marketplace_compute_window_rejects_invalid_unit_or_value(window):
    with pytest.raises(ValidationError):
        MarketplaceComputeWindow.model_validate(window)


@pytest.mark.parametrize("limit", [0, 21])
@pytest.mark.parametrize("metric", ["recent_reports", "report_search"])
def test_marketplace_compute_report_limit_is_bounded(metric, limit):
    query = {"metric": metric, "limit": limit}
    if metric == "report_search":
        query["query"] = "BTC"

    with pytest.raises(ValidationError):
        MarketplaceComputeQuery.model_validate(query)


def test_marketplace_compute_time_range_requires_from_before_to():
    with pytest.raises(ValidationError, match="time_range.from must be earlier"):
        MarketplaceComputeTimeRange.model_validate(
            {"from": "2026-07-17T12:00:00Z", "to": "2026-07-17T11:00:00Z"}
        )


async def test_marketplace_ai_compute_rejects_invalid_queries_before_http_request():
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={})

    client = MarketplaceAIClient(
        "https://market.example",
        transport=httpx.MockTransport(handler),
    )

    result = await client.compute_agent_metrics(
        ADDRESS,
        [{"metric": "volume_sum"}],
        viewer_context=VIEWER,
    )

    assert calls == 0
    assert result["status"] == "invalid_request"
    assert result["reason"] == "marketplace_queries_invalid"
    assert "volume_sum requires a valid window or time_range" in result["message"]


async def test_marketplace_ai_client_redacts_viewer_identity_from_success_and_errors():
    responses = iter(
        [
            httpx.Response(
                200,
                json={
                    "wallet": VIEWER.wallet,
                    "account": VIEWER.user_id,
                    "wallet_address_masked": "0xabcd...abcd",
                },
            ),
            httpx.Response(
                400,
                json={
                    "error": f"bad viewer {VIEWER.wallet}",
                    "message": f"bad account {VIEWER.user_id}",
                },
            ),
        ]
    )

    client = MarketplaceAIClient(
        "https://market.example",
        transport=httpx.MockTransport(lambda _request: next(responses)),
    )

    success = await client.get_agent_context(ADDRESS, viewer_context=VIEWER)
    failure = await client.get_agent_context(ADDRESS, viewer_context=VIEWER)
    rendered = repr((success, failure))

    assert VIEWER.wallet not in rendered
    assert VIEWER.user_id not in rendered
    assert "0xabcd...abcd" in rendered


async def test_marketplace_ai_client_returns_sanitized_unavailable_for_missing_base_url():
    client = MarketplaceAIClient("")

    result = await client.get_agent_context(ADDRESS)

    assert result == {
        "ok": False,
        "source": "marketplace_ai",
        "status": "unavailable",
        "reason": "marketplace_not_configured",
        "message": "Marketplace AI base URL is not configured.",
    }


async def test_marketplace_ai_client_sanitizes_http_error_payload():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": "ambiguous agent address, provide chain_id",
                "address": ADDRESS,
                "candidates": [{"agent_id": 1051, "chain_id": 999}],
                "debug_sql": "must-not-leak",
            },
        )

    client = MarketplaceAIClient(
        "https://market.example",
        transport=httpx.MockTransport(handler),
    )

    result = await client.get_agent_context(ADDRESS)

    rendered = repr(result)
    assert result["ok"] is False
    assert result["status"] == "invalid_request"
    assert "ambiguous agent address" in rendered
    assert "debug_sql" not in rendered
    assert "must-not-leak" not in rendered
