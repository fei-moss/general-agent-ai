# 2026-07-06 URL User UUID Chat API Implementation Plan

Specification: `SPEC-URL-USER-UUID-CHAT-API-001`

Target branch/baseline: `codex/zai-glm52-dockerhost`

Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`

## Scope Summary

Add Marketplace-facing `/api/v1/chat?user_uuid=...` backend routes, route-scoped URL identity extraction, versioned stream/ws URLs, and length validation that prevents long JWT-like identities from reaching `VARCHAR(64)` persistence columns.

## Out Of Scope

- Frontend or proxy changes.
- Database migrations.
- Formal auth or wallet identity.
- Release automation route migration unless requested separately.

## Change Steps

1. Focused red tests for URL identity contract
   - Files/modules: `tests/test_chat_routing.py`, `tests/test_stream_replay.py`, `tests/test_api_request_rate_limit.py`.
   - Behavior change: express `/api/v1/chat?user_uuid=...`, missing/overlong identity errors, returned versioned stream/ws URLs, WS query identity, and `/api/v1/chat` rate-limit coverage.
   - Data contract impact: none.
   - Tests to add/update: ASGI route tests and direct helper tests.
   - Verification command: `.venv/bin/python -m pytest tests/test_chat_routing.py tests/test_stream_replay.py tests/test_api_request_rate_limit.py -q`.
   - Rollback or compatibility note: tests protect additive route behavior while legacy route tests keep compatibility visible.

2. Middleware and dependency identity extraction
   - Files/modules: `app/api/middleware.py`, `app/api/deps.py`.
   - Behavior change: `/api/v1/*` derives identity only from `user_uuid`; legacy routes keep header fallback; both enforce `<=64` user id length.
   - Data contract impact: prevents overlong values from reaching persisted `user_id`.
   - Tests to add/update: missing/blank/overlong route tests.
   - Verification command: `.venv/bin/python -m pytest tests/test_chat_routing.py tests/test_api_request_rate_limit.py -q`.
   - Rollback or compatibility note: remove `/api/v1` branch and length guard only if a wider identity migration is implemented.

3. Versioned chat, run status, and stream routes
   - Files/modules: `app/api/routers/chat.py`, `app/api/routers/runs.py`, `app/api/routers/stream.py`.
   - Behavior change: add `/api/v1/chat`, `/api/v1/chat/runs/{run_id}`, `/api/v1/chat/runs/{run_id}/stream`, and `/api/v1/chat/runs/{run_id}/ws`; versioned accepted responses include encoded `user_uuid`.
   - Data contract impact: no response field changes, only relative URL values differ by route.
   - Tests to add/update: accepted response and stream identity helper coverage.
   - Verification command: `.venv/bin/python -m pytest tests/test_chat_routing.py tests/test_stream_replay.py -q`.
   - Rollback or compatibility note: legacy `/chat`, `/stream`, and `/ws` remain.

4. Documentation
   - Files/modules: `docs/API.md`, `docs/INTEGRATION_GUIDE.md`.
   - Behavior change: document Marketplace-facing `user_uuid` query identity and warn against forwarding raw JWTs as `user_id`.
   - Data contract impact: docs only.
   - Tests to add/update: none.
   - Verification command: manual review plus focused tests.
   - Rollback or compatibility note: keep legacy notes until callers migrate.

5. Review and verification
   - Files/modules: changed files.
   - Behavior change: defect-finding pass against `SPEC-URL-USER-UUID-CHAT-API-001`.
   - Data contract impact: none.
   - Tests to add/update: any missing regression found during review.
   - Verification command: `.venv/bin/python -m pytest tests/test_chat_routing.py tests/test_stream_replay.py tests/test_api_request_rate_limit.py -q`.
   - Rollback or compatibility note: run broader gates only after unrelated local chat-eval changes are reconciled or accepted.

## Risk Controls

- Public contract risks: keep legacy routes while adding versioned Marketplace route.
- Money/accounting/security risks: do not persist raw JWTs; reject overlong identities before DB writes.
- Migration/rebuild risks: no schema change.
- Performance risks: route and query parsing only.
- Deployment/test-branch risks: frontend/proxy must add `user_uuid` query before relying on the new route.
- Unrelated local changes to avoid: do not edit existing chat-eval closure files in the dirty worktree.

## Completion Criteria

- Specification still matches implementation.
- Red tests fail before implementation and pass after code changes.
- Focused tests pass.
- Review finds no unresolved contract or security issue.
- Deferred release automation/docs scope is explicitly called out if not changed.
