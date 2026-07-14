"""Resolve the trusted request owner at the Chat Server boundary.

Marketplace requests carry two headers injected by the authenticated gateway.
The normalized wallet is the storage/rate-limit owner while the Marketplace user
identifier remains available as account context. User-facing Chat routes have no
legacy identity fallback; `/rag/*` keeps its independent internal-admin contract.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal


IdentitySource = Literal["marketplace", "internal-admin"]

_BEARER_PREFIX = "Bearer "
_MARKETPLACE_USER_HEADER = "x-marketplace-user-id"
_MARKETPLACE_WALLET_HEADER = "x-marketplace-wallet"
_MAX_USER_ID_LENGTH = 64
_MARKETPLACE_USER_RE = re.compile(r"^marketplace:user:[1-9][0-9]*$")
_EVM_WALLET_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_RAG_PREFIX = "/rag"


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


def resolve_http_identity(request: Any) -> ResolvedIdentity:
    """Resolve one HTTP owner under the route-specific trust contract."""
    if _is_rag_path(request.url.path):
        return _resolve_internal_admin_headers(request.headers)
    marketplace = _resolve_marketplace_headers(request.headers)
    if marketplace is not None:
        return marketplace
    raise IdentityResolutionError(401, "MARKETPLACE_IDENTITY_REQUIRED")


def resolve_websocket_identity(websocket: Any) -> ResolvedIdentity:
    """Require the dedicated Marketplace identity on WebSocket handshakes."""
    marketplace = _resolve_marketplace_headers(websocket.headers)
    if marketplace is not None:
        return marketplace
    raise IdentityResolutionError(401, "MARKETPLACE_IDENTITY_REQUIRED")


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


def _resolve_internal_admin_headers(headers: Any) -> ResolvedIdentity:
    """Preserve the independent internal `/rag/*` admin identity contract."""
    auth = _header(headers, "authorization")
    if auth and auth.startswith(_BEARER_PREFIX):
        return _internal_admin_identity(
            auth[len(_BEARER_PREFIX) :],
            missing_detail="缺少鉴权凭证(Authorization Bearer 或 X-API-Key)",
        )
    api_key = _header(headers, "x-api-key")
    if api_key is not None:
        return _internal_admin_identity(
            api_key,
            missing_detail="缺少鉴权凭证(Authorization Bearer 或 X-API-Key)",
        )
    raise IdentityResolutionError(
        401, "缺少鉴权凭证(Authorization Bearer 或 X-API-Key)"
    )


def _internal_admin_identity(
    value: str | None,
    *,
    missing_detail: str,
) -> ResolvedIdentity:
    candidate = (value or "").strip()
    if not candidate:
        raise IdentityResolutionError(401, missing_detail)
    if len(candidate) > _MAX_USER_ID_LENGTH:
        raise IdentityResolutionError(422, "USER_ID_TOO_LONG")
    return ResolvedIdentity(owner_id=candidate, source="internal-admin")


def _header(headers: Any, name: str) -> str | None:
    value = headers.get(name)
    if value is None:
        value = headers.get(name.title())
    return value


def _is_rag_path(path: str) -> bool:
    return path == _RAG_PREFIX or path.startswith(f"{_RAG_PREFIX}/")
