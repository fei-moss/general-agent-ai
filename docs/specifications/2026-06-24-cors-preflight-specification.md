# 2026-06-24 CORS Preflight Specification

## Context

- Spec ID: `SPEC-CORS-PREFLIGHT-001`
- Workflow Class: `HARNESS-FOCUSED-CHANGE`
- Related specifications:
  - `SPEC-ASYNC-CHAT-ONLY-001`: `/chat` is an async-only accepted-run API.
  - `SPEC-CHAT-RUNTIME-001`: realtime Chat runtime and stream contract.
- PRD/source request:
  - Frontend reports a cross-origin failure when calling production `/chat`.
- Target baseline:
  - Current `codex/zai-glm52-dockerhost` worktree.
- Current behavior:
  - `create_app()` registers `CORSMiddleware` before `TraceIdMiddleware`, `AuthMiddleware`, and `RateLimitMiddleware`.
  - Starlette evaluates later-added middleware first, making CORS innermost.
  - Browser `OPTIONS` preflight for `/chat` can be handled by custom auth/rate middleware before CORS has a chance to return preflight headers.
- Problem:
  - Cross-origin browser clients need unauthenticated CORS preflight to succeed before sending `POST /chat` with `Authorization` and `Content-Type`.
  - CORS headers should also be attached to protected-route errors so browsers surface the actual HTTP error instead of a generic CORS failure.
- Non-goals:
  - No change to authentication requirements for real `POST /chat`.
  - No public API route, schema, event, provider, DB, or streaming contract changes.
  - No production origin allowlist tightening in this slice.

## Product Semantics

- User/operator workflow:
  - Browser frontend can preflight `OPTIONS /chat` from any origin currently allowed by the demo-wide CORS policy.
  - Browser frontend can send authenticated `POST /chat` after successful preflight.
- State model:
  - No run, conversation, message, idempotency, provider, Redis, or DB state is created by preflight.
- Ownership and identity rules:
  - `POST /chat` remains protected by `Authorization: Bearer <token>` or `X-API-Key`.
  - Preflight does not establish user identity.
- Permissions/authentication:
  - `OPTIONS` preflight is handled by CORS middleware without requiring application auth.
  - Non-preflight protected requests remain authenticated.
- Empty, error, retry, timeout, duplicate, and partial-failure behavior:
  - Unchanged.
- Compatibility and migration expectations:
  - Existing non-browser clients are unaffected.

## API / Interface Contract

- Routes, commands, events, jobs, or UI surfaces:
  - `OPTIONS /chat` with `Origin`, `Access-Control-Request-Method: POST`, and requested headers including `Authorization` and `Content-Type` returns a CORS preflight response.
  - `POST /chat` behavior is unchanged.
- Request fields and validation:
  - Unchanged.
- Response/envelope fields and types:
  - Preflight response includes `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods`, and `Access-Control-Allow-Headers`.
- Status/error codes:
  - Valid preflight should not return application `401`.
  - Protected `POST /chat` without auth still returns `401`.
- Pagination/sorting/filtering:
  - Unchanged.
- Backward compatibility:
  - CORS behavior becomes less brittle for browsers without relaxing real request auth.

## Data / Schema / Projection Impact

- Tables, indexes, migrations, backfills:
  - None.
- Read models, projections, snapshots, caches:
  - None.
- Rebuild or cleanup operators:
  - None.
- Historical data behavior:
  - Unchanged.
- Performance-sensitive queries or write paths:
  - Preflight must avoid DB/Redis/provider work.

## Architecture

- Modules/files expected to change:
  - `app/api/main.py`: register `CORSMiddleware` as the outermost middleware.
  - `tests/test_cors.py`: regression tests for preflight and protected POST auth.
  - `docs/API.md`: keep frontend CORS docs accurate.
- Data flow:
  1. Browser sends `OPTIONS /chat` preflight.
  2. Outermost `CORSMiddleware` handles the request and returns CORS headers.
  3. Browser sends the actual authenticated `POST /chat`.
  4. Normal trace, auth, rate-limit, route, and runtime behavior proceeds.
- Transaction/concurrency boundaries:
  - No new boundary.
- Observability/logging/metrics:
  - No new metric.
- Rollback strategy:
  - Revert middleware registration order and tests; no data rollback.

## Harness Classification

- Expected gate(s):
  - `HARNESS-FOCUSED-CHANGE`
  - Focused pytest
  - `scripts/check_ai_boundaries.sh`
  - `scripts/check_spec_contract.sh`
  - `scripts/check_harness_workflows.sh`
  - `scripts/verify_release.sh`
- Performance-sensitive class:
  - API middleware hot path; ordering-only change.
- Whether harness mapping must be extended:
  - No.
- Required performance evidence:
  - Focused test proves preflight does not enter auth/repo/runtime side effects.
- Focused verification commands:
  - `.venv/bin/python -m pytest tests/test_cors.py -q`
- Prerelease-grade verification commands:
  - `make test`
  - `AI_BOUNDARY_APPROVED=1 make verify-release`

## Acceptance Criteria

- Functional:
  - Browser-style `OPTIONS /chat` preflight returns non-401 and includes CORS headers.
  - Requested `Authorization` and `Content-Type` headers are allowed.
  - Unauthenticated `POST /chat` remains `401` and includes CORS response headers when an `Origin` is present.
- Edge cases:
  - Preflight creates no chat run or persistence side effects.
  - Public health/docs endpoints remain unchanged.
- Compatibility:
  - No request/response schema or event stream change.
- Operational:
  - No secrets, tokens, production origins, or private host credentials are committed.
- Evidence artifacts:
  - Specification and implementation plan.
  - Focused pytest output.
  - Release harness output or explicit blocker.

## Review Notes

- Open questions:
  - Production origin allowlist should be tightened later when frontend production origin(s) are finalized.
- Accepted assumptions:
  - The current demo-wide `allow_origins=["*"]` policy remains intentional for this slice.
  - Frontend sends `Authorization` rather than relying on cookies.
- Rejected alternatives:
  - Bypass auth for all `OPTIONS` inside `AuthMiddleware`: rejected because correct CORS placement also attaches CORS headers to application errors.
  - Add frontend-specific origin without knowing the frontend production URL: rejected as premature and likely to create another deployment-specific failure.

