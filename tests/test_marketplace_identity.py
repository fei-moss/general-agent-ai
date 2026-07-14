from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, Request
from starlette.requests import Request as StarletteRequest

from app.api.identity import (
    IdentityResolutionError,
    resolve_http_identity,
    resolve_websocket_identity,
)
from app.api.middleware import AuthMiddleware, RateLimitMiddleware
from app.api.ratelimit import RateLimitResult
from app.core.config import get_settings


USER_HEADER = "marketplace:user:7"
WALLET = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
MIXED_WALLET = "0xAbCdEfAbCdEfAbCdEfAbCdEfAbCdEfAbCdEfAbCd"


def _request(
    path: str = "/chat",
    *,
    query: str = "",
    headers: dict[str, str] | None = None,
) -> StarletteRequest:
    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    return StarletteRequest(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "raw_path": path.encode(),
            "query_string": query.encode(),
            "headers": raw_headers,
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1234),
            "scheme": "http",
        }
    )


def test_dedicated_marketplace_headers_override_every_legacy_identity():
    request = _request(
        query="user_uuid=caller-query",
        headers={
            "X-Marketplace-User-ID": USER_HEADER,
            "X-Marketplace-Wallet": MIXED_WALLET,
            "Authorization": "Bearer caller-header",
            "X-API-Key": "caller-api-key",
        },
    )

    resolved = resolve_http_identity(request)

    assert resolved.owner_id == WALLET
    assert resolved.source == "marketplace"
    assert resolved.marketplace_user_id == USER_HEADER
    assert resolved.marketplace_wallet == WALLET


@pytest.mark.parametrize(
    ("headers", "detail"),
    [
        ({"X-Marketplace-User-ID": USER_HEADER}, "MARKETPLACE_IDENTITY_INVALID"),
        ({"X-Marketplace-Wallet": WALLET}, "MARKETPLACE_IDENTITY_INVALID"),
        (
            {
                "X-Marketplace-User-ID": "marketplace:user:0",
                "X-Marketplace-Wallet": WALLET,
            },
            "MARKETPLACE_IDENTITY_INVALID",
        ),
        (
            {
                "X-Marketplace-User-ID": USER_HEADER,
                "X-Marketplace-Wallet": "not-a-wallet",
            },
            "MARKETPLACE_IDENTITY_INVALID",
        ),
    ],
)
def test_partial_or_malformed_marketplace_headers_fail_without_legacy_fallback(
    headers: dict[str, str], detail: str
):
    request = _request(query="user_uuid=legacy-user", headers=headers)

    with pytest.raises(IdentityResolutionError) as exc:
        resolve_http_identity(request)

    assert exc.value.status_code == 422
    assert exc.value.detail == detail


def test_chat_identity_rejects_legacy_only_identity_in_every_environment():
    request = _request(
        query="user_uuid=legacy-user",
        headers={"Authorization": "Bearer legacy-header"},
    )

    with pytest.raises(IdentityResolutionError) as exc:
        resolve_http_identity(request)

    assert exc.value.status_code == 401
    assert exc.value.detail == "MARKETPLACE_IDENTITY_REQUIRED"


@pytest.mark.parametrize(
    ("path", "query", "headers"),
    [
        ("/chat", "user_uuid=query-user", {}),
        (
            "/conversations",
            "",
            {"Authorization": "Bearer header-user"},
        ),
        (
            "/conversations",
            "",
            {"X-API-Key": "api-key-user"},
        ),
    ],
)
def test_legacy_inputs_never_authenticate_user_facing_chat_routes(
    path: str,
    query: str,
    headers: dict[str, str],
):
    with pytest.raises(IdentityResolutionError) as exc:
        resolve_http_identity(_request(path, query=query, headers=headers))

    assert exc.value.status_code == 401
    assert exc.value.detail == "MARKETPLACE_IDENTITY_REQUIRED"


def test_internal_rag_admin_identity_contract_remains_independent():
    resolved = resolve_http_identity(
        _request(
            "/rag/query",
            headers={"Authorization": "Bearer rag-admin"},
        )
    )

    assert resolved.owner_id == "rag-admin"
    assert resolved.source == "internal-admin"


def test_websocket_uses_marketplace_wallet_and_always_rejects_legacy():
    websocket = SimpleNamespace(
        url=SimpleNamespace(path="/ws/run-1"),
        query_params={"user_uuid": "query-user", "token": "query-token"},
        headers={
            "x-marketplace-user-id": USER_HEADER,
            "x-marketplace-wallet": MIXED_WALLET,
            "authorization": "Bearer header-user",
        },
    )

    resolved = resolve_websocket_identity(websocket)

    assert resolved.owner_id == WALLET
    assert resolved.source == "marketplace"

    legacy = SimpleNamespace(
        url=SimpleNamespace(path="/ws/run-1"),
        query_params={"user_uuid": "query-user"},
        headers={},
    )
    with pytest.raises(IdentityResolutionError) as exc:
        resolve_websocket_identity(legacy)
    assert exc.value.status_code == 401
    assert exc.value.detail == "MARKETPLACE_IDENTITY_REQUIRED"


@pytest.mark.asyncio
async def test_http_middleware_and_rate_limit_use_trusted_wallet():
    get_settings.cache_clear()

    class _Limiter:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def check(self, user_id: str, *, route: str) -> RateLimitResult:
            self.calls.append((user_id, route))
            return RateLimitResult(
                allowed=True,
                limit=60,
                remaining=59,
                retry_after=0,
            )

    limiter = _Limiter()
    app = FastAPI()
    app.state.rate_limiter = limiter
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AuthMiddleware)

    @app.post("/chat")
    async def _chat(request: Request):
        identity = getattr(request.state, "marketplace_identity", None)
        return {
            "owner": request.state.user_id,
            "source": request.state.user_id_source,
            "account": identity.marketplace_user_id if identity else None,
        }

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/chat?user_uuid=caller-query",
                headers={
                    "X-Marketplace-User-ID": USER_HEADER,
                    "X-Marketplace-Wallet": MIXED_WALLET,
                    "Authorization": "Bearer caller-header",
                },
            )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json() == {
        "owner": WALLET,
        "source": "marketplace",
        "account": USER_HEADER,
    }
    assert limiter.calls == [(WALLET, "/chat")]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("proxy_payload", "detail"),
    [
        ({}, "MARKETPLACE_IDENTITY_INVALID"),
        (
            {
                "marketplace_identity": {
                    "user_id": "not-a-marketplace-user",
                    "wallet_address": WALLET,
                }
            },
            "MARKETPLACE_IDENTITY_INVALID",
        ),
        (
            {
                "marketplace_identity": {
                    "user_id": "marketplace:user:8",
                    "wallet_address": WALLET,
                },
                "user_address": WALLET,
                "wallet_address": WALLET,
            },
            "MARKETPLACE_IDENTITY_MISMATCH",
        ),
        (
            {
                "marketplace_identity": {
                    "user_id": USER_HEADER,
                    "wallet_address": WALLET,
                },
                "user_address": "0x1111111111111111111111111111111111111111",
                "wallet_address": WALLET,
            },
            "MARKETPLACE_IDENTITY_MISMATCH",
        ),
    ],
)
async def test_marketplace_chat_rejects_invalid_or_mismatched_reserved_context_before_repos(
    proxy_payload: dict[str, object], detail: str
):
    from app.api import deps
    from app.api.main import create_app

    get_settings.cache_clear()
    app = create_app()

    async def repos_must_not_be_touched():
        yield object()

    app.dependency_overrides[deps.get_repos] = repos_must_not_be_touched
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/chat?user_uuid=caller-query",
                headers={
                    "X-Marketplace-User-ID": USER_HEADER,
                    "X-Marketplace-Wallet": MIXED_WALLET,
                    "Authorization": "Bearer caller-header",
                },
                json={"message": "hello", "proxy_payload": proxy_payload},
            )
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    assert response.status_code == 422
    assert response.json()["detail"] == detail
