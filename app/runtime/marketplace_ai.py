"""Marketplace AI read-only client and current-Agent context helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Literal

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.core.config import Settings

_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_MARKETPLACE_USER_RE = re.compile(r"^marketplace:user:[1-9][0-9]*$")
_MAX_REPORTS_LIMIT = 20
_MAX_QUERIES = 10
_BALLOT_PROPOSAL_FIELDS = (
    "title",
    "status",
    "voting_starts_at",
    "voting_ends_at",
)
BALLOT_DYNAMIC_CONTEXT_FIELDS = (
    "accrual_display_location", "airdrop_token", "concentration_note",
    "early_redeem_rule", "execution_rule", "fixed_apy", "gov_reward_detail",
    "governance_rewards_rule", "project_name", "project_token",
    "proposal_creation_rule", "proposal_display_location", "proposal_threshold",
    "redeem_during_vote_rule", "reward_source_summary", "snapshot_timing_rule",
    "vote_change_rule", "vote_cost_note", "voting_power_rule", "yield_denomination",
)
# Approval: owner-request:consumer-golden-regression-20260819
CONSUMER_DYNAMIC_CONTEXT_FIELDS: tuple[str, ...] = (
    "consumer_accept_token",
    "consumer_brand_name",
    "consumer_enterprise_eligibility",
    "consumer_feature_scope",
    "consumer_mint_fee",
    "consumer_minimum_mint_amount",
    "consumer_official_community_link",
    "consumer_official_support_channel",
    "consumer_price_comparison",
    "consumer_redemption_benefit",
    "consumer_redemption_code_expiry",
    "consumer_redemption_code_value",
    "consumer_redemption_entry",
    "consumer_redemption_threshold",
    "consumer_refund_fee",
    "consumer_support_email",
)

MarketplaceComputeMetric = Literal[
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


class MarketplaceComputeWindow(BaseModel):
    """Relative time window accepted by Marketplace compute."""

    model_config = ConfigDict(extra="forbid")

    unit: Literal["hour", "day"]
    value: int = Field(ge=1)


class MarketplaceComputeTimeRange(BaseModel):
    """Absolute UTC-compatible time range accepted by Marketplace compute."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_: datetime = Field(alias="from")
    to: datetime | None = None

    @field_validator("from_", "to")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("time_range timestamps must include a UTC offset")
        return value

    @model_validator(mode="after")
    def validate_order(self) -> MarketplaceComputeTimeRange:
        if self.to is not None and self.from_ >= self.to:
            raise ValueError("time_range.from must be earlier than time_range.to")
        return self


class MarketplaceComputeQuery(BaseModel):
    """One self-contained metric request for Marketplace compute."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    metric: MarketplaceComputeMetric
    window: MarketplaceComputeWindow | None = None
    time_range: MarketplaceComputeTimeRange | None = None
    limit: int | None = Field(default=None, ge=1, le=_MAX_REPORTS_LIMIT)
    query: str | None = None
    include_raw: bool = False

    @field_validator("id", "query", mode="before")
    @classmethod
    def strip_optional_text(cls, value: Any) -> Any:
        if value is None:
            return None
        return str(value).strip()

    @model_validator(mode="after")
    def validate_metric_requirements(self) -> MarketplaceComputeQuery:
        if (
            self.metric in {"volume_sum", "share_price_change"}
            and self.window is None
            and self.time_range is None
        ):
            raise ValueError(f"{self.metric} requires a valid window or time_range")
        if self.metric == "report_search" and not self.query:
            raise ValueError("report_search requires a non-empty query")
        return self


MarketplaceComputeQueries = Annotated[
    list[MarketplaceComputeQuery],
    Field(min_length=1, max_length=_MAX_QUERIES),
]


@dataclass(frozen=True)
class MarketplaceAgentRef:
    """Server-owned reference to the current Agent detail page."""

    address: str
    chain_id: int | None = None


@dataclass(frozen=True, slots=True, repr=False)
class MarketplaceViewerContext:
    """Trusted, server-only identity used for Marketplace tool execution."""

    user_id: str
    wallet: str
    agent_run_id: str
    conversation_id: str
    trace_id: str | None = None

    def __post_init__(self) -> None:
        user_id = str(self.user_id or "").strip()
        wallet = str(self.wallet or "").strip().lower()
        agent_run_id = str(self.agent_run_id or "").strip()
        conversation_id = str(self.conversation_id or "").strip()
        trace_id = str(self.trace_id or "").strip() or None
        if (
            _MARKETPLACE_USER_RE.fullmatch(user_id) is None
            or _ADDRESS_RE.fullmatch(wallet) is None
            or not agent_run_id
            or not conversation_id
        ):
            raise ValueError("invalid Marketplace viewer context")
        object.__setattr__(self, "user_id", user_id)
        object.__setattr__(self, "wallet", wallet)
        object.__setattr__(self, "agent_run_id", agent_run_id)
        object.__setattr__(self, "conversation_id", conversation_id)
        object.__setattr__(self, "trace_id", trace_id)

    def __repr__(self) -> str:
        return (
            "MarketplaceViewerContext("
            "user_id='[masked:identity]', wallet='[masked:identity]', "
            f"agent_run_id={self.agent_run_id!r}, "
            f"conversation_id={self.conversation_id!r}, trace_id={self.trace_id!r})"
        )

    def to_payload(self) -> dict[str, str]:
        payload = {
            "user_id": self.user_id,
            "wallet": self.wallet,
            "agent_run_id": self.agent_run_id,
            "conversation_id": self.conversation_id,
        }
        if self.trace_id is not None:
            payload["trace_id"] = self.trace_id
        return payload

    def matches_execution(
        self,
        *,
        agent_run_id: str,
        conversation_id: str,
        trace_id: str | None,
    ) -> bool:
        return (
            self.agent_run_id == agent_run_id
            and self.conversation_id == conversation_id
            and (self.trace_id is None or self.trace_id == trace_id)
        )

    @classmethod
    def from_payload(cls, payload: Any) -> MarketplaceViewerContext | None:
        if not isinstance(payload, dict):
            return None
        try:
            return cls(
                user_id=payload.get("user_id"),
                wallet=payload.get("wallet"),
                agent_run_id=payload.get("agent_run_id"),
                conversation_id=payload.get("conversation_id"),
                trace_id=payload.get("trace_id"),
            )
        except (TypeError, ValueError):
            return None


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

    @property
    def is_configured(self) -> bool:
        """Return whether Marketplace has a request base URL."""
        return bool(self._base_url)

    async def get_agent_context(
        self,
        address: str,
        *,
        viewer_context: MarketplaceViewerContext | None = None,
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
            viewer_context=viewer_context,
        )

    async def get_ballot_proposals(self, agent_id: int) -> dict[str, Any]:
        """Call the public GET /api/v1/ballot/agents/{agent_id}/proposals."""
        if not self._base_url:
            return marketplace_unavailable(
                "marketplace_not_configured",
                "Marketplace AI base URL is not configured.",
            )
        clean_agent_id = _clean_agent_id(agent_id)
        if clean_agent_id is None:
            return marketplace_unavailable(
                "marketplace_agent_id_invalid",
                "Current Ballot Agent ID is invalid.",
                status="invalid_request",
            )
        result = await self._request(
            "GET",
            f"/api/v1/ballot/agents/{clean_agent_id}/proposals",
            params={"limit": 10, "offset": 0},
        )
        return _project_ballot_proposal_fields(result)

    async def compute_agent_metrics(
        self,
        address: str,
        queries: list[MarketplaceComputeQuery | dict[str, Any]],
        *,
        viewer_context: MarketplaceViewerContext | None = None,
        chain_id: int | None = None,
    ) -> dict[str, Any]:
        """Call POST /api/v1/agents/{address}/ai-compute."""
        if viewer_context is None:
            return marketplace_unavailable(
                "marketplace_viewer_context_missing",
                "Trusted Marketplace viewer context is required for compute.",
            )
        try:
            normalized_queries = normalize_compute_queries(queries)
        except ValueError as exc:
            return marketplace_unavailable(
                "marketplace_queries_invalid",
                str(exc),
                status="invalid_request",
            )
        if not self._base_url:
            return marketplace_unavailable(
                "marketplace_not_configured",
                "Marketplace AI base URL is not configured.",
            )
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
            viewer_context=viewer_context,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        viewer_context: MarketplaceViewerContext | None = None,
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout_s,
                transport=self._transport,
            ) as client:
                headers = {"Accept": "application/json"}
                if viewer_context is not None:
                    headers.update(_viewer_headers(viewer_context))
                response = await client.request(
                    method,
                    path,
                    params=params,
                    json=json_body,
                    headers=headers,
                )
            try:
                payload = response.json()
            except ValueError:
                return marketplace_unavailable(
                    "marketplace_invalid_json",
                    "Marketplace returned a non-JSON response.",
                )
            payload = _redact_viewer_identity(payload, viewer_context)
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


def annotate_ballot_context_availability(result: dict[str, Any]) -> dict[str, Any]:
    """Add typed Ballot availability without inventing missing values."""
    payload = result.get("data") if isinstance(result, dict) else None
    agent = payload.get("agent") if isinstance(payload, dict) else None
    if not (
        result.get("ok") is True
        and isinstance(agent, dict)
        and str(agent.get("agent_type") or "").strip().casefold() == "ballot"
    ):
        return result
    direct = {
        "project_name": (agent.get("name"), "agent.name"),
        "project_token": (agent.get("accept_token_symbol"), "agent.accept_token_symbol"),
    }
    typed: dict[str, dict[str, Any]] = {}
    for field in BALLOT_DYNAMIC_CONTEXT_FIELDS:
        if field in direct:
            value, source = direct[field]
        elif field in agent:
            value, source = agent.get(field), f"agent.{field}"
        else:
            value, source = None, "marketplace_agent_context"
        available = value is not None and bool(str(value).strip())
        typed[field] = {
            "availability": "available" if available else "not_provided",
            "value": value if available else None,
            "source": source,
        }
    return {**result, "data": {**payload, "ballot_governance": typed}}


def _viewer_headers(context: MarketplaceViewerContext) -> dict[str, str]:
    headers = {
        "X-Marketplace-User-ID": context.user_id,
        "X-Marketplace-Wallet": context.wallet,
        "X-Agent-Run-ID": context.agent_run_id,
        "X-Conversation-ID": context.conversation_id,
    }
    if context.trace_id is not None:
        headers["X-Trace-ID"] = context.trace_id
    return headers


def _redact_viewer_identity(
    value: Any,
    context: MarketplaceViewerContext | None,
) -> Any:
    if context is None:
        return value
    if isinstance(value, dict):
        return {
            _redact_viewer_identity(key, context): _redact_viewer_identity(item, context)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_viewer_identity(item, context) for item in value]
    if not isinstance(value, str):
        return value
    redacted = re.sub(
        re.escape(context.wallet),
        "[masked:identity]",
        value,
        flags=re.IGNORECASE,
    )
    return re.sub(
        re.escape(context.user_id),
        "[masked:identity]",
        redacted,
        flags=re.IGNORECASE,
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


def extract_current_ballot_agent_id(
    marketplace_context_result: dict[str, Any] | None,
) -> int | None:
    """Extract the positive Agent ID returned by Marketplace ``ai-context``."""
    if (
        not isinstance(marketplace_context_result, dict)
        or marketplace_context_result.get("ok") is not True
    ):
        return None
    payload = marketplace_context_result.get("data")
    agent = payload.get("agent") if isinstance(payload, dict) else None
    if not isinstance(agent, dict):
        return None
    agent_id = _clean_agent_id(agent.get("id"))
    if agent_id is not None:
        return agent_id
    return _clean_agent_id(agent.get("agent_id"))


def normalize_compute_queries(queries: Any) -> list[dict[str, Any]]:
    """Validate and serialize a bounded Marketplace compute query list."""
    if not isinstance(queries, list):
        return []
    if len(queries) > _MAX_QUERIES:
        raise ValueError(f"Marketplace compute accepts at most {_MAX_QUERIES} queries")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(queries):
        try:
            query = (
                item
                if isinstance(item, MarketplaceComputeQuery)
                else MarketplaceComputeQuery.model_validate(item)
            )
        except ValidationError as exc:
            first_error = exc.errors(include_url=False)[0]
            message = str(first_error.get("msg") or "invalid compute query")
            if message.startswith("Value error, "):
                message = message.removeprefix("Value error, ")
            raise ValueError(f"queries[{index}]: {message}") from exc
        normalized.append(
            query.model_dump(
                mode="json",
                by_alias=True,
                exclude_none=True,
                exclude_defaults=True,
            )
        )
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


def _clean_agent_id(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    match = re.fullmatch(r"#?([1-9][0-9]*)", str(value or "").strip())
    return int(match.group(1)) if match is not None else None


def _project_ballot_proposal_fields(result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict) or result.get("ok") is not True:
        return result
    payload = result.get("data")
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return marketplace_unavailable(
            "marketplace_proposals_not_returned",
            "Current proposal instance data was not returned.",
        )
    projected = [
        {
            field: item[field]
            for field in _BALLOT_PROPOSAL_FIELDS
            if field in item
        }
        for item in items
        if isinstance(item, dict)
    ]
    return {**result, "data": {"items": projected}}


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
