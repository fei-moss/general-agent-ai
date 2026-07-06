"""Marketplace AI read-only client and current-Agent context helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings

_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_MAX_REPORTS_LIMIT = 20
_MAX_QUERIES = 10


@dataclass(frozen=True)
class MarketplaceAgentRef:
    """Server-owned reference to the current Agent detail page."""

    address: str
    chain_id: int | None = None


class MarketplaceAIClient:
    """Async client for Marketplace's ai-chat read-only endpoints."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_s: float = 8.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = (base_url or "").strip().rstrip("/")
        self._timeout_s = timeout_s
        self._transport = transport

    async def get_agent_context(
        self,
        address: str,
        *,
        chain_id: int | None = None,
        reports_limit: int = 5,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        """Call GET /api/v1/agents/{address}/ai-context."""
        if not self._base_url:
            return marketplace_unavailable(
                "marketplace_not_configured",
                "Marketplace AI base URL is not configured.",
            )
        params: dict[str, Any] = {
            "reports_limit": _bounded_int(reports_limit, default=5, min_value=0, max_value=_MAX_REPORTS_LIMIT),
            "include_raw": "true" if include_raw else "false",
        }
        if chain_id is not None:
            params["chain_id"] = chain_id
        return await self._request(
            "GET",
            f"/api/v1/agents/{address}/ai-context",
            params=params,
        )

    async def compute_agent_metrics(
        self,
        address: str,
        queries: list[dict[str, Any]],
        *,
        chain_id: int | None = None,
    ) -> dict[str, Any]:
        """Call POST /api/v1/agents/{address}/ai-compute."""
        if not self._base_url:
            return marketplace_unavailable(
                "marketplace_not_configured",
                "Marketplace AI base URL is not configured.",
            )
        normalized_queries = normalize_compute_queries(queries)
        if not normalized_queries:
            return marketplace_unavailable(
                "marketplace_queries_missing",
                "Marketplace compute requires at least one metric query.",
                status="invalid_request",
            )
        params = {"chain_id": chain_id} if chain_id is not None else None
        return await self._request(
            "POST",
            f"/api/v1/agents/{address}/ai-compute",
            params=params,
            json_body={"queries": normalized_queries},
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout_s,
                transport=self._transport,
            ) as client:
                response = await client.request(
                    method,
                    path,
                    params=params,
                    json=json_body,
                    headers={"Accept": "application/json"},
                )
            try:
                payload = response.json()
            except ValueError:
                return marketplace_unavailable(
                    "marketplace_invalid_json",
                    "Marketplace returned a non-JSON response.",
                )
            if response.status_code >= 400:
                return {
                    "ok": False,
                    "source": "marketplace_ai",
                    "status": _http_status_label(response.status_code),
                    "reason": f"marketplace_http_{response.status_code}",
                    "message": _message_from_error(payload, response.status_code),
                    "data": _sanitized_error_payload(payload),
                }
            return {
                "ok": True,
                "source": "marketplace_ai",
                "data": payload,
            }
        except httpx.TimeoutException:
            return marketplace_unavailable(
                "marketplace_timeout",
                "Marketplace AI request timed out.",
            )
        except httpx.HTTPError:
            return marketplace_unavailable(
                "marketplace_http_error",
                "Marketplace AI request failed.",
            )


def build_marketplace_ai_client(settings: Settings) -> MarketplaceAIClient:
    """Build the configured Marketplace AI client."""
    return MarketplaceAIClient(
        getattr(settings, "marketplace_ai_base_url", ""),
        timeout_s=float(getattr(settings, "marketplace_ai_timeout_s", 8.0)),
    )


def extract_current_agent_ref(
    run_context: dict[str, Any] | None,
) -> MarketplaceAgentRef | None:
    """Extract the current Agent reference from server-owned run context."""
    context = run_context or {}
    candidates: list[Any] = []
    for key in ("marketplace_agent", "agent"):
        value = context.get(key)
        if isinstance(value, dict):
            candidates.extend([value.get("address"), value.get("contract_address")])
    candidates.extend([context.get("agent_address"), context.get("contract_address")])
    for address in candidates:
        clean_address = _clean_address(address)
        if clean_address is None:
            continue
        return MarketplaceAgentRef(address=clean_address, chain_id=None)
    return None


def normalize_compute_queries(queries: list[dict[str, Any]] | Any) -> list[dict[str, Any]]:
    """Return a bounded, pass-through query list for Marketplace compute."""
    if not isinstance(queries, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in queries[:_MAX_QUERIES]:
        if not isinstance(item, dict):
            continue
        metric = str(item.get("metric") or "").strip()
        if not metric:
            continue
        query: dict[str, Any] = {"metric": metric}
        for field in (
            "id",
            "window",
            "time_range",
            "limit",
            "query",
            "include_raw",
        ):
            if field in item:
                query[field] = item[field]
        normalized.append(query)
    return normalized


def marketplace_unavailable(
    reason: str,
    message: str,
    *,
    status: str = "unavailable",
) -> dict[str, Any]:
    """Return a sanitized Marketplace tool failure."""
    return {
        "ok": False,
        "source": "marketplace_ai",
        "status": status,
        "reason": reason,
        "message": message,
    }


def current_agent_missing_result() -> dict[str, Any]:
    """Return the structured error used when no current Agent is configured."""
    return marketplace_unavailable(
        "CURRENT_AGENT_ADDRESS_MISSING",
        "Current Agent address is missing from server run_context.",
    )


def _clean_address(value: Any) -> str | None:
    address = str(value or "").strip()
    if not _ADDRESS_RE.match(address):
        return None
    return address


def _bounded_int(
    value: Any,
    *,
    default: int,
    min_value: int,
    max_value: int,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(min_value, min(max_value, parsed))


def _http_status_label(status_code: int) -> str:
    if status_code == 400:
        return "invalid_request"
    if status_code == 404:
        return "not_found"
    return "unavailable"


def _message_from_error(payload: Any, status_code: int) -> str:
    if isinstance(payload, dict):
        message = payload.get("message") or payload.get("error")
        if message:
            return str(message)
    return f"Marketplace AI request failed with HTTP {status_code}."


def _sanitized_error_payload(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    allowed: dict[str, Any] = {}
    for field in ("error", "message", "address", "candidates"):
        if field in payload:
            allowed[field] = payload[field]
    return allowed or None
