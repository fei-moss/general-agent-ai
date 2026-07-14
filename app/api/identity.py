"""Resolve the trusted request owner at the Chat Server boundary.

Marketplace requests carry two headers injected by the authenticated gateway.
The normalized wallet is the storage/rate-limit owner while the Marketplace user
identifier remains available as account context.  Legacy caller-supplied identities
remain available only in the explicit development compatibility mode.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal


IdentitySource = Literal["marketplace", "user_uuid", "header"]
IdentityMode = Literal["legacy-compatible", "marketplace"]

_BEARER_PREFIX = "Bearer "
_MARKETPLACE_USER_HEADER = "x-marketplace-user-id"
_MARKETPLACE_WALLET_HEADER = "x-marketplace-wallet"
_URL_USER_QUERY = "user_uuid"
_MAX_USER_ID_LENGTH = 64
_MARKETPLACE_USER_RE = re.compile(r"^marketplace:user:[1-9][0-9]*$")
_EVM_WALLET_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_CHAT_FLOW_PATHS = ("/chat",)
_CHAT_FLOW_PREFIXES = ("/stream/", "/ws/", "/runs/")


@dataclass(frozen=True, slots=True)
class ResolvedIdentity:
    """Validated owner identity attached to one inbound request."""

    owner_id: str
    source: IdentitySource
    marketplace_user_id: str | None = None
    marketplace_wallet: str | None = None


class IdentityResolutionError(ValueError):
    """Identity failure with the HTTP status and stable public detail code."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def resolve_http_identity(request: Any, mode: IdentityMode) -> ResolvedIdentity:
    """Resolve HTTP identity, preferring trusted Marketplace headers."""
    marketplace = _resolve_marketplace_headers(request.headers)
    if marketplace is not None:
        return marketplace
    if mode == "marketplace":
        raise IdentityResolutionError(401, "MARKETPLACE_IDENTITY_REQUIRED")

    if _is_chat_flow(request.url.path) and _URL_USER_QUERY in request.query_params:
        return _legacy_identity(
            request.query_params.get(_URL_USER_QUERY),
            source="user_uuid",
            missing_detail="缺少 user_uuid",
            too_long_detail="USER_UUID_TOO_LONG",
        )
    return _resolve_legacy_headers(request.headers)


def resolve_websocket_identity(websocket: Any, mode: IdentityMode) -> ResolvedIdentity:
    """Resolve WebSocket identity using the same trust boundary as HTTP."""
    marketplace = _resolve_marketplace_headers(websocket.headers)
    if marketplace is not None:
        return marketplace
    if mode == "marketplace":
        raise IdentityResolutionError(401, "MARKETPLACE_IDENTITY_REQUIRED")

    if _URL_USER_QUERY in websocket.query_params:
        return _legacy_identity(
            websocket.query_params.get(_URL_USER_QUERY),
            source="user_uuid",
            missing_detail="缺少 user_uuid",
            too_long_detail="USER_UUID_TOO_LONG",
        )
    token = websocket.query_params.get("token")
    if token is not None:
        return _legacy_identity(
            token,
            source="header",
            missing_detail="缺少鉴权凭证",
            too_long_detail="USER_ID_TOO_LONG",
        )
    return _resolve_legacy_headers(websocket.headers)


def _resolve_marketplace_headers(headers: Any) -> ResolvedIdentity | None:
    user_id = _header(headers, _MARKETPLACE_USER_HEADER)
    wallet = _header(headers, _MARKETPLACE_WALLET_HEADER)
    if user_id is None and wallet is None:
        return None
    if user_id is None or wallet is None:
        raise IdentityResolutionError(422, "MARKETPLACE_IDENTITY_INVALID")

    user_id = user_id.strip()
    wallet = wallet.strip()
    if (
        len(user_id) > _MAX_USER_ID_LENGTH
        or _MARKETPLACE_USER_RE.fullmatch(user_id) is None
        or _EVM_WALLET_RE.fullmatch(wallet) is None
    ):
        raise IdentityResolutionError(422, "MARKETPLACE_IDENTITY_INVALID")
    normalized_wallet = wallet.lower()
    return ResolvedIdentity(
        owner_id=normalized_wallet,
        source="marketplace",
        marketplace_user_id=user_id,
        marketplace_wallet=normalized_wallet,
    )


def _resolve_legacy_headers(headers: Any) -> ResolvedIdentity:
    auth = _header(headers, "authorization")
    if auth and auth.startswith(_BEARER_PREFIX):
        return _legacy_identity(
            auth[len(_BEARER_PREFIX) :],
            source="header",
            missing_detail="缺少鉴权凭证(Authorization Bearer 或 X-API-Key)",
            too_long_detail="USER_ID_TOO_LONG",
        )
    api_key = _header(headers, "x-api-key")
    if api_key is not None:
        return _legacy_identity(
            api_key,
            source="header",
            missing_detail="缺少鉴权凭证(Authorization Bearer 或 X-API-Key)",
            too_long_detail="USER_ID_TOO_LONG",
        )
    raise IdentityResolutionError(
        401, "缺少鉴权凭证(Authorization Bearer 或 X-API-Key)"
    )


def _legacy_identity(
    value: str | None,
    *,
    source: Literal["user_uuid", "header"],
    missing_detail: str,
    too_long_detail: str,
) -> ResolvedIdentity:
    candidate = (value or "").strip()
    if not candidate:
        raise IdentityResolutionError(401, missing_detail)
    if len(candidate) > _MAX_USER_ID_LENGTH:
        raise IdentityResolutionError(422, too_long_detail)
    return ResolvedIdentity(owner_id=candidate, source=source)


def _header(headers: Any, name: str) -> str | None:
    value = headers.get(name)
    if value is None:
        value = headers.get(name.title())
    return value


def _is_chat_flow(path: str) -> bool:
    return path in _CHAT_FLOW_PATHS or any(
        path.startswith(prefix) for prefix in _CHAT_FLOW_PREFIXES
    )
