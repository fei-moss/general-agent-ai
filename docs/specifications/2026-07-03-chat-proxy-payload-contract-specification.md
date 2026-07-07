# 2026-07-03 Chat Proxy Payload Contract Specification

Spec ID: `SPEC-CHAT-PROXY-PAYLOAD-CONTRACT-001`

Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`

## Context

- PRD/source request: upstream/proxy integrations submit generic page context through `proxy_payload`; current Agent page identity may also arrive in trusted `metadata.agent_context` / `metadata.current_agent_address` fields on `POST /chat`.
- Target baseline: current `codex/zai-glm52-dockerhost` branch with `SPEC-PLATFORM-MECHANISM-ABSORPTION-001` generic `run_context` propagation already implemented.
- Current behavior: the internal runtime carries context through idempotency hashing, run plan masking, realtime/batch payloads, provider preflight estimates, and runtime tool routing.
- Problem: upstream integration examples use `proxy_payload`, while the service currently exposes a `run_context` request field. Active Marketplace callers now also send current Agent page context under `metadata`, so the runtime must project that trusted metadata into the same effective context used by tools.
- Non-goals:
  - No new database column, migration, event type, stream shape, or Marketplace tool contract.
  - No personal wallet secret ingestion; callers must pass only minimal, sanitized context.
  - No runtime rename below the API schema boundary; existing internal runtime names can remain `run_context`.

## Product Semantics

- User/operator workflow: upstream services call `POST /chat` with `proxy_payload` for generic context and `metadata.agent_context` / `metadata.current_agent_address` for trusted current Agent page context.
- State model: `proxy_payload` is the generic external context envelope. Trusted current Agent metadata is normalized into the existing effective `run_context` for one run as `agent_address` plus `agent`.
- Ownership and identity rules: authentication remains header-derived. Context is scoped to the accepted run and must not imply authenticated wallet ownership unless upstream explicitly supplies sanitized page state.
- Current Agent trust rules: `metadata.agent_context` and `metadata.current_agent_address` are trusted as page context from the upstream Marketplace UI, but they do not replace authentication and must not be treated as proof of wallet ownership.
- Permissions/authentication: unchanged from `POST /chat`.
- Empty, error, retry, timeout, duplicate, and partial-failure behavior:
  - Empty or omitted `proxy_payload` behaves like an empty context.
  - `run_context` is not accepted in the external request body.
  - Idempotency hashes use the normalized effective context so context changes cannot replay an unrelated run.
- Compatibility and migration expectations: callers must use `proxy_payload`; old `run_context` request bodies fail validation.

## API / Interface Contract

- Route: `POST /chat`.
- Request fields:
  - `proxy_payload: object = {}` is accepted as the upstream context envelope.
  - `metadata.agent_context: object` is accepted as trusted current Agent page context.
  - `metadata.current_agent_address: string` is accepted as the preferred current Agent address when present.
  - `run_context` is rejected when present in the request body.
- Response/envelope fields and types: unchanged `202 ChatAccepted`.
- Status/error codes:
  - `422` for request bodies containing `run_context`.
  - Existing `422 STREAM_FALSE_NOT_SUPPORTED`, `409`, `429`, `503`, and auth behavior remain unchanged.
- Backward compatibility: existing request bodies that omit context remain valid; `run_context` compatibility is intentionally removed.

## Data / Schema / Projection Impact

- Tables, indexes, migrations, backfills: none.
- Read models, projections, snapshots, caches: accepted run plans still store masked effective context under `run_context`.
- Historical data behavior: old runs are unchanged.
- Performance-sensitive paths: provider preflight token estimates include the normalized effective context, including metadata-derived Agent context, as before.

## Architecture

- Modules/files expected to change:
  - `app/core/schemas.py`
  - `app/api/routers/chat.py` tests only if effective context access needs adjustment
  - `docs/API.md`
  - `docs/INTEGRATION_GUIDE.md`
  - focused tests under `tests/`
- Data flow:
  1. Client sends `proxy_payload` and may send `metadata.agent_context` / `metadata.current_agent_address`.
  2. `ChatRequest` validates the request and exposes a normalized internal effective context accessor.
  3. The effective context merges generic `proxy_payload` with metadata-derived current Agent fields, preferring `metadata.current_agent_address` over addresses in `metadata.agent_context`.
  4. Existing chat acceptance, idempotency, provider preflight, payload dispatch, and runtime tools consume the effective context.
- Transaction/concurrency boundaries: unchanged.
- Observability/logging/metrics: run plan masking remains the redaction boundary.
- Rollback strategy: restore `run_context` request-field compatibility if an active caller is found; no data rollback.

## Harness Classification

- Expected gate(s): `HARNESS-SPEC-FIRST-FEATURE`.
- Performance-sensitive class: low; request parsing and hashing only.
- Whether harness mapping must be extended: no.
- Required performance evidence: focused unit tests cover normalization and propagation; release gate can be run before deployment.
- Focused verification commands:
  - `.venv/bin/python -m pytest tests/test_chat_routing.py tests/test_idempotency_and_lock.py -q`
- Prerelease-grade verification commands:
  - `make test`
  - `make verify-release`

## Acceptance Criteria

- Functional:
  - `ChatRequest(proxy_payload=...)` accepts object context and exposes the same effective content to the runtime.
  - `ChatRequest(metadata.agent_context/current_agent_address=...)` exposes metadata-derived `agent_address` and `agent` in the runtime context without requiring `proxy_payload`.
  - `POST /chat` payload building forwards `proxy_payload` context to realtime/batch execution as `run_context`.
  - Provider preflight estimates include generic `proxy_payload` and metadata-derived Agent context after normalization.
  - Requests containing `run_context` are rejected.
- Edge cases:
  - Empty or omitted `proxy_payload` is accepted.
  - Unknown fields other than `run_context` keep the existing default Pydantic behavior.
- Compatibility:
  - `ChatAccepted`, SSE, WebSocket, run status, and conversation history shapes are unchanged.
- Operational:
  - Documentation examples use valid JSON without comments.
- Evidence artifacts:
  - Focused tests pass.

## Review Notes

- Accepted assumptions:
  - `proxy_payload` is the user-facing upstream field name for generic context; `metadata.agent_context` and `metadata.current_agent_address` are the trusted current Agent page context fields for active Marketplace callers.
  - Internal runtime modules may still call the normalized effective context `run_context`.
  - Upstream will pass sanitized page/Agent context, not private keys or unrelated wallet data.
- Rejected alternatives:
  - Accepting `run_context` as a request alias was rejected because upstream should have a single external context field.
