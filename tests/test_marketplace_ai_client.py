from __future__ import annotations

import json

import httpx

from app.runtime.marketplace_ai import (
    MarketplaceAIClient,
    extract_current_agent_ref,
)


ADDRESS = "0x17B09FC949f031dbD540D4caDE59805A08Ee5043"


def test_extract_current_agent_ref_uses_server_owned_run_context():
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
    assert ref.chain_id == 999


def test_extract_current_agent_ref_rejects_missing_or_invalid_address():
    assert extract_current_agent_ref({}) is None
    assert extract_current_agent_ref({"agent_address": "not-an-address"}) is None


async def test_marketplace_ai_context_builds_documented_get_request():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "agent": {"id": 1051, "contract_address": ADDRESS},
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
        chain_id=999,
        reports_limit=200,
        include_raw=True,
    )

    assert result["ok"] is True
    assert result["source"] == "marketplace_ai"
    assert result["data"]["agent"]["id"] == 1051
    request = seen[0]
    assert request.method == "GET"
    assert request.url.path == f"/api/v1/agents/{ADDRESS}/ai-context"
    assert request.url.params["chain_id"] == "999"
    assert request.url.params["reports_limit"] == "20"
    assert request.url.params["include_raw"] == "true"


async def test_marketplace_ai_compute_builds_documented_post_request():
    seen_body: dict | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_body
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
    result_item = result["data"]["results"][0]
    assert result_item["available"] is False
    assert result_item["status"] == "unsupported"
    assert result_item["reason"] == "pnl_not_defined"


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
