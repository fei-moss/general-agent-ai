# 2026-07-06 URL User UUID Chat API Specification

Spec ID: `SPEC-URL-USER-UUID-CHAT-API-001`

Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`

## Context

- PRD/source request: Marketplace chat integration should identify the caller by appending `user_uuid` to the existing chat URL instead of forwarding a long Authorization token as the Chat Server user id.
- Clarification: `/api/v1/chat` was an incorrect extra route family. The contract must use the existing `/chat` route and existing `/stream`, `/ws`, and `/runs` follow-up routes.
- Target baseline: current `codex/zai-glm52-dockerhost` branch.
- Current behavior: `POST /chat`, `/stream/{run_id}`, `/ws/{run_id}`, `/runs/{run_id}`, and `/conversations/*` derive `user_id` from `Authorization: Bearer <token>` or `X-API-Key`.
- Problem: the Marketplace proxy can forward a long JWT-like identity as `Authorization`, or can append a long JWT-like value as `user_uuid`; either must not reach `idempotency_record.user_id VARCHAR(64)` as a durable user id.
- Non-goals:
  - No database schema migration.
  - No formal auth, OAuth, API key, wallet ownership, or tenant system.
  - No frontend implementation in this slice.
  - No change to RAG/admin header authentication.

## Product Semantics

- User/operator workflow: upstream Marketplace services call `POST /chat?user_uuid=<user_uuid>` with a stable short internal user id in the query string.
- State model: URL `user_uuid` becomes the internal `user_id` for conversations, idempotency records, rate limiting, provider preflight, task payloads, stream ownership checks, run status checks, and conversation ownership checks.
- Ownership and identity rules:
  - Existing chat-flow routes use URL query `user_uuid` as the preferred identity when present.
  - Chat-flow routes are `/chat`, `/stream/{agent_run_id}`, `/ws/{agent_run_id}`, and `/runs/{agent_run_id}`.
  - Header-derived identity remains a compatibility fallback for direct/internal callers on existing routes.
  - If both URL `user_uuid` and headers are present on chat-flow routes, URL `user_uuid` wins.
  - The removed `/api/v1/chat` route family must not be registered and should return `404`.
- Permissions/authentication:
  - `user_uuid` is an opaque caller-provided short id, not necessarily an RFC 4122 UUID.
  - `user_uuid` must be non-blank and fit the persisted `user_id` column (`<=64` characters).
  - Header-derived legacy user ids must also fit `<=64` characters to avoid DB truncation failures.
- Empty, error, retry, timeout, duplicate, and partial-failure behavior:
  - Missing URL `user_uuid` on `/chat` is allowed only when a valid legacy identity header is present.
  - Overlong URL `user_uuid` returns `422 USER_UUID_TOO_LONG` before repository writes, even if a header is also present.
  - Overlong header-derived user id returns `422 USER_ID_TOO_LONG` before repository writes when URL `user_uuid` is absent.
  - Existing idempotency conflict, owner mismatch, provider limiter, async-only, realtime capacity, and stream replay behavior remain unchanged.
- Compatibility and migration expectations:
  - No new Marketplace route is added.
  - Existing `/chat` callers can migrate by adding `?user_uuid=<short-id>`.
  - Legacy header-derived routes remain available for now but are guarded against overlong user ids.

## API / Interface Contract

- Routes:
  - `POST /chat?user_uuid=<user_uuid>`
  - `GET /runs/{agent_run_id}?user_uuid=<user_uuid>`
  - `GET /stream/{agent_run_id}?user_uuid=<user_uuid>`
  - `WS /ws/{agent_run_id}?user_uuid=<user_uuid>`
  - Legacy `/chat`, `/runs/{agent_run_id}`, `/stream/{agent_run_id}`, and `/ws/{agent_run_id}` remain usable with short header identity.
  - `/api/v1/chat`, `/api/v1/chat/runs/{id}`, `/api/v1/chat/runs/{id}/stream`, and `/api/v1/chat/runs/{id}/ws` are not part of the contract.
- Request fields and validation:
  - Chat body remains `message`, optional `conversation_id`, optional `stream`, optional `metadata`, optional `conversation_anchor`, and `proxy_payload`.
  - Query `user_uuid`, when present, must be non-blank and must be `<=64` characters.
  - Legacy header-derived user id must be `<=64` characters.
- Response/envelope fields and types:
  - `ChatAccepted` field names and types remain unchanged.
  - `/chat?user_uuid=...` accepted responses return legacy relative `stream_url` and `ws_url` paths with the same encoded `user_uuid` appended.
  - `/chat` accepted responses without URL `user_uuid` keep legacy relative `stream_url` and `ws_url` without query parameters.
- Status/error codes:
  - Removed `/api/v1/chat*` routes: `404`.
  - Overlong URL `user_uuid`: `422 USER_UUID_TOO_LONG`.
  - Overlong legacy header user id: `422 USER_ID_TOO_LONG`.
  - Existing `401`, `422 STREAM_FALSE_NOT_SUPPORTED`, `409`, `429`, `503`, and `403` owner errors remain unchanged.
- Pagination/sorting/filtering: unchanged.
- Backward compatibility: existing `/chat` route remains; query `user_uuid` is additive on that route.

## Data / Schema / Projection Impact

- Tables, indexes, migrations, backfills: none.
- Read models, projections, snapshots, caches: none.
- Rebuild or cleanup operators: none.
- Historical data behavior: existing conversations and runs remain keyed by their stored `user_id`; callers must use the same short identity to recover them.
- Performance-sensitive queries or write paths: no new query shape; rate limiting still scopes to `/chat`.

## Architecture

- Modules/files expected to change:
  - `app/api/middleware.py`
  - `app/api/deps.py`
  - `app/api/routers/chat.py`
  - `app/api/routers/runs.py`
  - `app/api/routers/stream.py`
  - focused tests under `tests/`
  - `docs/API.md` and `docs/INTEGRATION_GUIDE.md`
- Data flow:
  1. Middleware extracts URL `user_uuid` for chat-flow HTTP routes and writes it to `request.state.user_id`.
  2. If URL `user_uuid` is absent, middleware falls back to short header-derived identity for compatibility.
  3. `CurrentUser` dependency returns request-state identity.
  4. Existing chat acceptance, idempotency, repository writes, provider preflight, realtime/batch dispatch, and owner checks use that internal `user_id`.
  5. Accepted responses include `user_uuid` on stream/ws URLs only when the chat request used URL `user_uuid`.
  6. WebSocket performs the same URL `user_uuid` preference during handshake because it does not use HTTP middleware.
- Transaction/concurrency boundaries: unchanged.
- Observability/logging/metrics: do not log raw Authorization tokens; URL and header overlong identities are rejected before persistence.
- Rollback strategy: callers can keep using `/chat` with short header identity; remove query-identity extraction if Marketplace rollout is reverted.

## Harness Classification

- Expected gate(s): `HARNESS-SPEC-FIRST-FEATURE`.
- Performance-sensitive class: low; identity extraction and response URL query handling only.
- Whether harness mapping must be extended: no.
- Required performance evidence: focused API tests for route/auth behavior and rate-limit route coverage.
- Focused verification commands:
  - `.venv/bin/python -m pytest tests/test_chat_routing.py tests/test_stream_replay.py tests/test_api_request_rate_limit.py -q`
- Prerelease-grade verification commands:
  - `make test`
  - `make verify-release`

## Acceptance Criteria

- Functional:
  - `POST /chat?user_uuid=<short-id>` accepts a valid chat body without Authorization headers and returns `202`.
  - Accepted response includes legacy `stream_url` and `ws_url` with the same encoded `user_uuid`.
  - `/runs/{agent_run_id}?user_uuid=<short-id>` authorizes by URL `user_uuid`.
  - `/stream/{agent_run_id}?user_uuid=<short-id>` and `/ws/{agent_run_id}?user_uuid=<short-id>` authorize by URL `user_uuid`.
  - `POST /chat?user_uuid=<short-id>` ignores an overlong or unrelated Authorization header because URL identity wins.
  - Legacy `/chat` remains usable with short header identity.
  - `/api/v1/chat*` is not registered.
- Edge cases:
  - Missing URL `user_uuid` plus missing legacy headers returns the existing missing-auth `401`.
  - Overlong URL `user_uuid` returns `422 USER_UUID_TOO_LONG`.
  - Overlong legacy header-derived user id returns `422 USER_ID_TOO_LONG` before persistence.
- Compatibility:
  - RAG/admin/provider Authorization headers are unaffected.
  - Legacy chat-flow routes remain during migration.
- Operational:
  - Documentation shows `user_uuid` on `/chat`, not on `/api/v1/chat`.
  - No secrets or raw JWTs are printed, stored in docs, or logged by new tests.
- Evidence artifacts:
  - Focused tests pass.
  - Release gate passes before deploy.

## Review Notes

- Open questions: none for this correction.
- Accepted assumptions:
  - Marketplace can provide a stable short internal user id and URL-encode it as `user_uuid`.
  - Keeping header fallback on `/chat` reduces migration risk while the frontend/proxy is updated.
- Rejected alternatives:
  - Adding `/api/v1/chat` was rejected by user clarification.
  - Widening `user_id` columns was rejected because raw JWTs should not become durable user ids.
  - Hashing all Authorization tokens server-side was rejected for this slice because the user explicitly requested URL `user_uuid` on the chat route.
- Reviewer findings and resolution: pending implementation review.
