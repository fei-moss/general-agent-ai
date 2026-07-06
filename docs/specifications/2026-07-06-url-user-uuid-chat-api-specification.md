# 2026-07-06 URL User UUID Chat API Specification

Spec ID: `SPEC-URL-USER-UUID-CHAT-API-001`

Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`

## Context

- PRD/source request: Marketplace chat integration should identify the caller the same way `world-cup-chat-server` does: by appending `user_uuid` to the chat URL instead of forwarding a long Authorization token as the Chat Server user id.
- Target baseline: current `codex/zai-glm52-dockerhost` branch.
- Current behavior: `POST /chat`, `/stream/{run_id}`, `/ws/{run_id}`, `/runs/{run_id}`, and `/conversations/*` derive `user_id` from `Authorization: Bearer <token>` or `X-API-Key`.
- Problem: the Marketplace proxy can forward a long JWT-like identity as `Authorization`, which later reaches `idempotency_record.user_id VARCHAR(64)` and fails with a backend 500 instead of a stable client error or short user identity.
- Non-goals:
  - No database schema migration.
  - No formal auth, OAuth, API key, wallet ownership, or tenant system.
  - No frontend implementation in this slice.
  - No change to RAG/admin header authentication.

## Product Semantics

- User/operator workflow: upstream Marketplace services call `POST /api/v1/chat?user_uuid=<user_uuid>` with a stable short internal user id in the query string.
- State model: URL `user_uuid` becomes the internal `user_id` for conversations, idempotency records, rate limiting, provider preflight, task payloads, stream ownership checks, run status checks, and conversation ownership checks.
- Ownership and identity rules:
  - `/api/v1/*` chat-flow routes use URL query `user_uuid` as identity.
  - Header-only identity is not accepted for `/api/v1/*` chat-flow routes.
  - Legacy `/chat`, `/stream/*`, `/ws/*`, `/runs/*`, and `/conversations/*` may keep header-derived identity for direct/internal callers during migration.
- Permissions/authentication:
  - `user_uuid` is an opaque caller-provided short id, not necessarily an RFC 4122 UUID.
  - `user_uuid` must be non-blank and fit the persisted `user_id` column (`<=64` characters).
  - Header-derived legacy user ids must also fit `<=64` characters to avoid DB truncation failures.
- Empty, error, retry, timeout, duplicate, and partial-failure behavior:
  - Missing or blank `/api/v1/*` `user_uuid` returns `401`.
  - Overlong `user_uuid` or legacy header user id returns `422` before repository writes.
  - Existing idempotency conflict, owner mismatch, provider limiter, async-only, realtime capacity, and stream replay behavior remain unchanged.
- Compatibility and migration expectations:
  - New Marketplace-facing route is additive.
  - Legacy header-derived routes remain available for now but are guarded against overlong user ids.

## API / Interface Contract

- Routes:
  - `POST /api/v1/chat?user_uuid=<user_uuid>`
  - `GET /api/v1/chat/runs/{agent_run_id}?user_uuid=<user_uuid>`
  - `GET /api/v1/chat/runs/{agent_run_id}/stream?user_uuid=<user_uuid>`
  - `WS /api/v1/chat/runs/{agent_run_id}/ws?user_uuid=<user_uuid>`
  - Legacy `/chat`, `/stream/{agent_run_id}`, `/ws/{agent_run_id}` remain.
- Request fields and validation:
  - Chat body remains `message`, optional `conversation_id`, optional `stream`, optional `metadata`, optional `conversation_anchor`, and `proxy_payload`.
  - Query `user_uuid` is required for `/api/v1/*`, must be non-blank, and must be `<=64` characters.
  - Legacy header-derived user id must be `<=64` characters.
- Response/envelope fields and types:
  - `ChatAccepted` field names and types remain unchanged.
  - `/api/v1/chat` accepted responses return versioned relative `stream_url` and `ws_url` containing the same encoded `user_uuid`.
  - Legacy `/chat` accepted responses keep legacy relative `stream_url` and `ws_url`.
- Status/error codes:
  - Missing or blank `/api/v1/*` `user_uuid`: `401`.
  - Overlong `user_uuid` or legacy header user id: `422`.
  - Existing `422 STREAM_FALSE_NOT_SUPPORTED`, `409`, `429`, `503`, and `403` owner errors remain unchanged.
- Pagination/sorting/filtering: unchanged.
- Backward compatibility: legacy routes remain; new Marketplace-facing route is additive.

## Data / Schema / Projection Impact

- Tables, indexes, migrations, backfills: none.
- Read models, projections, snapshots, caches: none.
- Rebuild or cleanup operators: none.
- Historical data behavior: existing conversations and runs remain keyed by their stored `user_id`; callers must use the same short identity to recover them.
- Performance-sensitive queries or write paths: no new query shape; rate limiting gains the `/api/v1/chat` path.

## Architecture

- Modules/files expected to change:
  - `app/api/middleware.py`
  - `app/api/deps.py`
  - `app/api/routers/chat.py`
  - `app/api/routers/stream.py`
  - focused tests under `tests/`
  - `docs/API.md` and `docs/INTEGRATION_GUIDE.md`
- Data flow:
  1. Middleware extracts URL `user_uuid` for `/api/v1/*` and writes it to `request.state.user_id`.
  2. `CurrentUser` dependency returns request-state identity.
  3. Existing chat acceptance, idempotency, repository writes, provider preflight, realtime/batch dispatch, and owner checks use that internal `user_id`.
  4. Versioned accepted responses include `user_uuid` on stream/ws URLs.
- Transaction/concurrency boundaries: unchanged.
- Observability/logging/metrics: do not log raw Authorization tokens; legacy overlong identity is rejected before persistence.
- Rollback strategy: callers can keep using legacy `/chat` with short header identity; remove `/api/v1` router additions if Marketplace rollout is reverted.

## Harness Classification

- Expected gate(s): `HARNESS-SPEC-FIRST-FEATURE`.
- Performance-sensitive class: low; identity extraction and route aliases only.
- Whether harness mapping must be extended: no.
- Required performance evidence: focused API tests for route/auth behavior and rate-limit route coverage.
- Focused verification commands:
  - `.venv/bin/python -m pytest tests/test_chat_routing.py tests/test_stream_replay.py tests/test_api_request_rate_limit.py -q`
- Prerelease-grade verification commands:
  - `make test`
  - `make verify-release`

## Acceptance Criteria

- Functional:
  - `POST /api/v1/chat?user_uuid=<short-id>` accepts a valid chat body without Authorization headers and returns `202`.
  - Accepted response includes versioned `stream_url` and `ws_url` with the same encoded `user_uuid`.
  - Versioned run status endpoint authorizes by URL `user_uuid`.
  - Versioned SSE and WS endpoints authorize by URL `user_uuid`.
  - `/api/v1/chat` with header-only identity is rejected before side effects.
  - Legacy `/chat` remains usable with short header identity.
- Edge cases:
  - Missing/blank `/api/v1/*` `user_uuid` returns `401`.
  - Overlong `/api/v1/*` `user_uuid` returns `422`.
  - Overlong legacy header-derived user id returns `422` before persistence.
- Compatibility:
  - RAG/admin/provider Authorization headers are unaffected.
  - Legacy chat-flow routes remain during migration.
- Operational:
  - Documentation shows `user_uuid` as the Marketplace-facing identity path.
  - No secrets or raw JWTs are printed, stored in docs, or logged by new tests.
- Evidence artifacts:
  - Focused tests pass.

## Review Notes

- Open questions:
  - Whether release automation should switch its smoke path to `/api/v1/chat` in the same release or a later ops slice.
- Accepted assumptions:
  - Marketplace can provide a stable short internal user id and URL-encode it as `user_uuid`.
  - Keeping legacy `/chat` reduces migration risk while the frontend/proxy is updated.
- Rejected alternatives:
  - Widening `user_id` columns was rejected because raw JWTs should not become durable user ids.
  - Hashing all Authorization tokens server-side was rejected for this slice because the user explicitly requested the URL `user_uuid` integration shape.
  - Removing legacy `/chat` immediately was rejected to avoid breaking direct smoke and internal callers before the frontend change lands.
