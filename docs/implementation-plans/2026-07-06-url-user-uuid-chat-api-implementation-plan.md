# 2026-07-06 URL User UUID Chat API Implementation Plan

Specification: `SPEC-URL-USER-UUID-CHAT-API-001`

Target branch/baseline: `codex/zai-glm52-dockerhost`

Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`

## Scope Summary

Remove the incorrectly added `/api/v1/chat` route family and apply Marketplace URL `user_uuid` identity to the existing `/chat`, `/runs`, `/stream`, and `/ws` chat-flow routes. Preserve short header identity as a compatibility fallback and reject overlong URL/header identities before persistence.

## Out Of Scope

- Frontend or proxy changes.
- Database migrations.
- Formal auth or wallet identity.
- Changing RAG/admin/provider header authentication.

## Change Steps

1. Focused tests for corrected URL identity contract
   - Files/modules: `tests/test_chat_routing.py`, `tests/test_stream_replay.py`, `tests/test_api_request_rate_limit.py`.
   - Behavior change: express `/chat?user_uuid=...`, returned legacy stream/ws URLs carrying `user_uuid`, URL identity precedence over headers, removed `/api/v1/chat*` returning `404`, WS query identity, and `/chat` rate-limit coverage.
   - Data contract impact: none.
   - Tests to add/update: ASGI route tests and direct helper tests.
   - Verification command: `.venv/bin/python -m pytest tests/test_chat_routing.py tests/test_stream_replay.py tests/test_api_request_rate_limit.py -q`.
   - Rollback or compatibility note: tests protect the existing `/chat` route while documenting query identity as additive.

2. Middleware and dependency identity extraction
   - Files/modules: `app/api/middleware.py`, `app/api/deps.py`.
   - Behavior change: chat-flow HTTP routes prefer URL `user_uuid`; legacy routes keep header fallback; both enforce `<=64` user id length. Removed `/api/v1/chat*` paths bypass auth/rate-limit so FastAPI returns `404`.
   - Data contract impact: prevents overlong values from reaching persisted `user_id`.
   - Tests to add/update: overlong URL/header and removed-route tests.
   - Verification command: `.venv/bin/python -m pytest tests/test_chat_routing.py tests/test_api_request_rate_limit.py -q`.
   - Rollback or compatibility note: remove URL-preference branch only if the Marketplace route contract changes again.

3. Existing chat, run status, and stream routes
   - Files/modules: `app/api/routers/chat.py`, `app/api/routers/runs.py`, `app/api/routers/stream.py`.
   - Behavior change: remove `/api/v1/chat` decorators; accepted `/chat?user_uuid=...` responses include encoded query parameters on `/stream/{id}` and `/ws/{id}`; `/runs/{id}` and SSE use middleware identity; WS handshake prefers `user_uuid`.
   - Data contract impact: no response field changes, only relative URL values include query parameters when URL identity is used.
   - Tests to add/update: accepted response, ASGI chat/run status, and stream identity helper coverage.
   - Verification command: `.venv/bin/python -m pytest tests/test_chat_routing.py tests/test_stream_replay.py -q`.
   - Rollback or compatibility note: `/chat`, `/stream`, `/ws`, and `/runs` remain the only chat-flow route family.

4. Documentation
   - Files/modules: `docs/API.md`, `docs/INTEGRATION_GUIDE.md`.
   - Behavior change: document Marketplace-facing `user_uuid` on `/chat` and warn against forwarding raw JWTs as `user_uuid` or durable `user_id`.
   - Data contract impact: docs only.
   - Tests to add/update: none.
   - Verification command: manual review plus focused tests.
   - Rollback or compatibility note: remove stale `/api/v1/chat` examples.

5. Review and verification
   - Files/modules: changed files.
   - Behavior change: defect-finding pass against `SPEC-URL-USER-UUID-CHAT-API-001`.
   - Data contract impact: none.
   - Tests to add/update: any missing regression found during review.
   - Verification command: `.venv/bin/python -m pytest tests/test_chat_routing.py tests/test_stream_replay.py tests/test_api_request_rate_limit.py -q`, then release gate.
   - Rollback or compatibility note: deploy only after release gate and live smoke.

## Risk Controls

- Public contract risks: remove the unintended route family and keep all behavior on the already deployed `/chat` path.
- Money/accounting/security risks: do not persist raw JWTs; reject overlong identities before DB writes.
- Migration/rebuild risks: no schema change.
- Performance risks: route and query parsing only.
- Deployment/test-branch risks: upstream/proxy must pass a short stable `user_uuid`, not a JWT-like token.
- Unrelated local changes to avoid: keep staging scoped to this API contract correction.

## Completion Criteria

- Specification still matches implementation.
- Focused tests pass.
- Required harness/release gates pass.
- Review finds no unresolved contract or security issue.
- Commit, push, deploy, and live smoke use the corrected `/chat?user_uuid=...` contract.
