# 2026-07-14 Trusted Marketplace Chat Boundary Specification

Spec ID: `SPEC-TRUSTED-MARKETPLACE-CHAT-BOUNDARY-001`

Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`

Parent cross-repository contract: `agent_marketplace/docs/specifications/2026-07-14-global-auth-and-trusted-chat-boundary-specification.md` (`SPEC-GLOBAL-AUTH-TRUSTED-CHAT-BOUNDARY-001`).

This repository-local specification defines the Chat Server portion of the parent contract. It must not weaken the Marketplace global-auth requirements or change the approved frontend contract.

## PRD Audit

### Covered

- Marketplace is the public authentication authority.
- Chat Server is an internal downstream module in production.
- Marketplace supplies trusted account and wallet context through reserved `proxy_payload` plus plain internal headers.
- No service JWT, HMAC signature, mTLS requirement, or application-level encryption is introduced.
- Development may keep a public DockerHost Chat URL as an explicitly accepted non-production exception.
- Production must remove direct public Chat reachability.
- Frontend Chat calls remain unchanged because the frontend only calls Marketplace.

### Missing

- None that block this specification.

### Conflicts Resolved

- Existing URL `user_uuid` is caller-controlled and currently overrides headers on Chat flow routes. Marketplace-originated identity will instead come from dedicated internal headers.
- Existing `/conversations` uses a different identity source from create/run/stream. The trusted wallet will be used consistently for all Marketplace-originated routes.
- Existing batch continuation lacks the realtime owner check. Owner checks will be route-type independent.
- Current development deployment is public. That is accepted only for development and cannot satisfy the production release boundary.

### Accepted Assumptions

- Chat history remains scoped to the authenticated wallet already used by existing Marketplace-created conversations.
- Marketplace supplies normalized lowercase wallet addresses.
- Production private networking, rather than a service credential, establishes trust in Marketplace headers and reserved payload context.
- There are no supported direct Chat callers or partially migrated callers. Development tests may inject the same dedicated Marketplace headers directly.

### Go / No-Go

- Go for Specification drafting and repository-local planning.
- No-go for production release until the private network boundary is externally verified.

## Context

- PRD/source request:
  - Align Chat ownership with Marketplace login state without changing the frontend Chat API.
  - Let Marketplace inject all runtime user/wallet context needed by Chat.
  - Keep the integration simple because Chat Server is a downstream module rather than a public product API.
- Target baseline: `codex/zai-glm52-dockerhost` at `176745bc036ada7f1951dd1170463b456ca248f4`.
- Current behavior:
  - `/chat`, `/runs/*`, `/stream/*`, and `/ws/*` prefer query `user_uuid` and treat it as owner identity.
  - `/conversations/*` uses raw Bearer or `X-API-Key` content instead.
  - No identity input is cryptographically validated by Chat Server.
  - Conversation owner, idempotency, anchors, provider checks, task payloads, and API limiting reuse these caller-provided strings.
  - Realtime continuation checks existing conversation owner; batch continuation can reuse an existing conversation without the same check.
  - Run and stream owner checks are indirect through the parent conversation and do not consistently fail closed when parent state is missing.
- Problem:
  - Marketplace-created resources can be keyed differently across create and read routes.
  - Self-asserted identity is unsuitable when Chat is directly reachable.
  - Resource-level owner enforcement is incomplete even after a trusted upstream identity is available.
- Non-goals:
  - No frontend route, payload, response, SSE event, or WebSocket event change.
  - No independent end-user login/session system in Chat Server.
  - No Marketplace-to-Chat service token or signature.
  - No schema migration or merge of histories across multiple wallets.
  - No RAG admin-role redesign.
  - No change to Pydantic AI orchestration responsibilities or provider quota semantics.

## Product Semantics

### Trust Boundary

- Marketplace authenticates the browser and is the only supported production caller of Chat Server user-facing routes.
- Chat Server does not validate Marketplace user JWTs and does not accept frontend login tokens as its user database.
- Production trust comes from private network reachability: only Marketplace can reach Chat Server.
- Development may expose Chat through a public DockerHost URL without a service credential. This is a deliberate development exception, not a production guarantee.
- Every environment uses the same application identity contract; development does not enable a legacy Chat identity fallback.

### Marketplace Identity Inputs

- Marketplace supplies on every upstream request:
  - `X-Marketplace-User-ID: marketplace:user:<positive id>`;
  - `X-Marketplace-Wallet: <lowercase EVM wallet>`.
- Marketplace-originated `POST /chat` also supplies:

```json
{
  "proxy_payload": {
    "marketplace_identity": {
      "user_id": "marketplace:user:123",
      "wallet_address": "0x1234567890abcdef1234567890abcdef12345678"
    },
    "user_address": "0x1234567890abcdef1234567890abcdef12345678",
    "wallet_address": "0x1234567890abcdef1234567890abcdef12345678"
  }
}
```

- `proxy_payload.marketplace_identity` is a reserved server-owned namespace.
- `user_address` and `wallet_address` remain populated for existing runtime/tool compatibility, but their values are set by Marketplace.
- Chat Server normalizes and validates header shape. It does not treat these plain values as proof when the service is publicly reachable; they are trusted only under the approved deployment boundary.
- On create, header and reserved payload values must match after normalization.

### Identity Precedence and Compatibility

- For Marketplace-originated requests, `X-Marketplace-Wallet` is the authoritative Chat owner identity.
- `X-Marketplace-User-ID` is retained as account context and is not the persisted Chat owner key in this change.
- Marketplace no longer relies on query `user_uuid`, raw `Authorization`, `X-API-Key`, or WebSocket query `token`.
- Chat Server has one identity mode in every environment: both dedicated Marketplace headers are mandatory on user-facing Chat routes.
- URL `user_uuid`, raw `Authorization`, `X-API-Key`, and WebSocket query `token` cannot authenticate a user-facing Chat request. If present alongside valid dedicated headers they are ignored for ownership.
- Conflicting reserved Marketplace header/body context is rejected.

### Ownership

- The normalized trusted wallet is used consistently for:
  - conversation owner;
  - conversation list/detail filtering;
  - run status owner checks;
  - SSE and WebSocket owner checks;
  - idempotency scope;
  - conversation-anchor scope;
  - provider preflight user scope;
  - API request-rate-limit identity;
  - realtime and batch task payload user identity where existing runtime contracts expect owner id.
- Account context may be carried separately in run context or structured plan metadata, subject to existing masking rules.
- A conversation id supplied to `POST /chat` is checked against the trusted wallet before any route-specific capacity, lock, write, or dispatch behavior.
- The same owner check applies to realtime, auto-degraded-to-batch, explicitly batch, and forced-Celery routes.
- Repository conversation reuse must accept owner as part of the lookup or assert owner before returning an existing row.
- Null-owner conversations are denied through Marketplace-originated flow.
- Runs whose parent conversation is missing or has a different owner are not readable or streamable.

### Runtime Context

- The full trusted identity object is runtime context, not a prompt instruction.
- Runtime/tool code may read the wallet for wallet-scoped Marketplace AI calls.
- Model prompts must not expose raw internal account ids or full wallet addresses unless an existing masked product contract explicitly requires display.
- Existing Agent page context under `metadata.agent_context` remains separate from authenticated user identity.
- Agent page context does not prove wallet ownership.

### Environment Semantics

- Development/test:
  - separate Marketplace and Chat DockerHost environments are allowed;
  - public Chat URL is allowed for integration;
  - no service credential is required;
  - the same dedicated Marketplace headers are mandatory;
  - release notes must label this topology as development-only.
- Production:
  - Chat Server runs behind private networking;
  - no public `web` ingress or frontend-visible Chat base URL exists;
  - Marketplace calls Chat over the private address;
  - external negative reachability smoke is mandatory.
- Application behavior must not claim that a public development endpoint is authenticated merely because it understands Marketplace headers.

### Error, Retry, and Partial Failure

- Missing Marketplace identity on a Marketplace integration request returns `401 MARKETPLACE_IDENTITY_REQUIRED`.
- Malformed user id or wallet returns `422 MARKETPLACE_IDENTITY_INVALID`.
- Header/body mismatch returns `422 MARKETPLACE_IDENTITY_MISMATCH` before persistence.
- Cross-owner conversation, run, or stream access keeps the existing `403` owner-denial contract.
- Missing resource keeps existing `404` behavior.
- Idempotency replay is scoped to the trusted wallet and does not cross owners.
- Identity validation failure creates no conversation, message, run, task, anchor, or idempotency record.
- Existing provider, queue, realtime-capacity, disconnect, replay, and terminal-event behavior remains unchanged.

## API / Interface Contract

### Routes

- Existing internal paths remain:
  - `POST /chat`;
  - `GET /runs/{agent_run_id}`;
  - `GET /stream/{agent_run_id}`;
  - `WS /ws/{agent_run_id}`;
  - `POST /conversations`;
  - `GET /conversations`;
  - `GET /conversations/{conversation_id}`.
- No `/api/v1/chat*` route family is added to Chat Server.

### Request Contract

- Dedicated internal headers:
  - `X-Marketplace-User-ID`, required for Marketplace flow and max 64 characters;
  - `X-Marketplace-Wallet`, required for Marketplace flow and a valid EVM address.
- `POST /chat` reserved context:
  - `proxy_payload.marketplace_identity.user_id` equals `X-Marketplace-User-ID`;
  - `proxy_payload.marketplace_identity.wallet_address` equals `X-Marketplace-Wallet`;
  - `proxy_payload.user_address` and `proxy_payload.wallet_address` equal the trusted wallet when present.
- Existing request body fields and validation remain otherwise unchanged.
- URL `user_uuid`, raw `Authorization`, `X-API-Key`, and WebSocket query `token` are unsupported as user-facing Chat identity inputs.

### Response and Event Contract

- `ChatAccepted` field names and types remain unchanged.
- Marketplace-facing accepted responses do not need `user_uuid` appended to returned stream/ws URLs because Marketplace exposes its own stream URL.
- Existing SSE/WebSocket event names, JSON data shapes, replay cursor behavior, and terminal behavior remain unchanged.
- Conversation and run response schemas remain unchanged.

### Status Codes

- `401 MARKETPLACE_IDENTITY_REQUIRED`.
- `422 MARKETPLACE_IDENTITY_INVALID`.
- `422 MARKETPLACE_IDENTITY_MISMATCH`.
- Existing `403`, `404`, `409`, `422 STREAM_FALSE_NOT_SUPPORTED`, `429`, and `503` behaviors remain unless this specification explicitly tightens a missing-parent case.

### Pagination

- Conversation `limit` and `offset` semantics remain unchanged.
- Owner filtering occurs before limit/offset.

### Backward Compatibility

- Marketplace frontend compatibility is mandatory.
- Existing wallet-owned conversations require no data rewrite.
- Legacy direct Chat callers are intentionally unsupported; the owner confirmed that no such callers exist and no migration period is required.

## Data / Schema / Projection Impact

- No database schema migration.
- Existing `conversation.user_id` remains the wallet owner column for Marketplace-created data.
- Conversation anchors and idempotency records remain wallet-scoped.
- Existing wallet-owned conversations remain readable.
- Null-owner rows are not implicitly adopted by a Marketplace wallet.
- No RAG, vector, event-stream, task-state, or provider-usage schema change.
- No projection rebuild or cache flush.
- Owner-aware repository queries must not add unbounded fan-out.

## Architecture

### Modules Expected to Change

- `app/api/middleware.py`: Marketplace header extraction, precedence, validation, request-state identity source.
- `app/api/deps.py`: trusted Marketplace identity dependency behavior.
- `app/core/schemas.py`: reserved Marketplace identity validation/accessor if needed.
- `app/api/routers/chat.py`: consistent owner validation before realtime/batch branching and trusted context propagation.
- `app/api/repos.py`: owner-aware conversation reuse/query.
- `app/api/routers/conversations.py`: trusted-wallet create/list/detail ownership.
- `app/api/routers/runs.py`: fail-closed parent/owner check.
- `app/api/routers/stream.py`: SSE/WS trusted-wallet ownership and identity precedence.
- `app/api/ratelimit.py` or middleware wiring only as needed to use the trusted wallet consistently.
- `docs/API.md`, `docs/INTEGRATION_GUIDE.md`, production/DockerHost runbooks.
- Focused API, repository, stream, WebSocket, rate-limit, compatibility, and security tests.

### Data Flow

1. Marketplace validates frontend JWT.
2. Marketplace builds server-owned reserved identity context and internal headers.
3. Chat middleware validates the dedicated headers and stores trusted wallet plus account context.
4. `POST /chat` validates reserved body context against headers.
5. Chat owner checks occur before route selection side effects.
6. Repositories read/write using trusted wallet owner.
7. Runner/task/runtime receives trusted wallet and masked account context as required.
8. Follow-up run/conversation/stream routes use the same header-derived wallet.

### Transaction and Concurrency Boundaries

- Identity and owner validation happen before idempotency claim, conversation lock, realtime capacity reservation, database writes, or task dispatch.
- Existing transaction commit boundaries remain unless owner-aware reuse requires a narrower atomic query.
- Concurrent continuation still uses the existing conversation lock after ownership succeeds.

### Observability

- Preserve Marketplace trace id across requests.
- Record identity source and mismatch reason with low-cardinality labels.
- Never log raw headers, raw reserved identity payload, full wallet, or arbitrary Authorization content.
- Rate-limit storage continues to hash owner identity.

### Rollout

1. Add dedicated header/payload support and owner fixes.
2. Remove legacy user-facing Chat identity inputs and the environment mode switch.
3. Deploy to the existing development Chat environment.
4. Deploy Marketplace forwarding changes and run cross-service smoke.
5. Before production, move Chat behind private networking and remove public ingress.

### Rollback

- Roll back to the last compatible Chat commit if Marketplace forwarding fails.
- No data rollback is required.
- Production rollback must not reintroduce a public Chat endpoint without explicit owner approval.

## Harness Classification

- Expected gate: `HARNESS-SPEC-FIRST-FEATURE`.
- Performance-sensitive class: low.
- Harness mapping extension: not expected.
- Required feedback sources:
  - focused API/repository/stream tests;
  - adversarial owner review;
  - full pytest;
  - release harness;
  - Marketplace-to-Chat development smoke;
  - production network reachability smoke before promotion.
- Focused verification commands:
  - `.venv/bin/python -m pytest -q tests/test_chat_routing.py tests/test_stream_replay.py tests/test_api_request_rate_limit.py tests/test_db_repositories.py`.
  - `.venv/bin/python -m pytest -q tests/test_marketplace_identity.py tests/test_chat_owner_authorization.py`.
- Prerelease verification:
  - `.venv/bin/python -m pytest -q`.
  - `scripts/check_ai_boundaries.sh`.
  - `scripts/check_spec_contract.sh`.
  - `scripts/check_harness_workflows.sh`.
  - `scripts/verify_release.sh`.

## Acceptance Criteria

### Functional

1. Dedicated Marketplace headers are mandatory on every user-facing Chat request in every environment.
2. Marketplace reserved body identity is available as runtime context and matches the headers.
3. The trusted wallet is used for every owner-scoped Chat surface.
4. Conversation list and detail return the same wallet-owned conversations created through `/chat`.
5. Realtime, batch, forced-batch, and auto-degraded requests all reject cross-owner conversation ids before side effects.
6. Run, SSE, and WS access require a present parent conversation owned by the trusted wallet.
7. Existing frontend-visible Chat response and event contracts remain unchanged through Marketplace.

### Edge Cases

1. Missing, malformed, or mismatched Marketplace identity fails before persistence.
2. Legacy `user_uuid`, Authorization, API key, or WS token cannot authenticate a user-facing Chat request.
3. Null-owner resources are denied.
4. Idempotency cannot replay another wallet's run.
5. Owner filtering precedes pagination.
6. Identity errors do not leak full account or wallet values.

### Compatibility

1. Existing Marketplace-created wallet-owned data remains readable without migration.
2. Unsupported legacy direct Chat callers receive `401 MARKETPLACE_IDENTITY_REQUIRED` without side effects.
3. Existing provider, runner, queue, replay, and guardrail behavior remains unchanged.

### Operational

1. Focused tests, full tests, spec-contract checks, and release gate pass.
2. Development runbook labels public Chat reachability as an accepted non-production exception.
3. Production runbook requires no public Chat ingress; no identity mode switch exists.
4. Cross-service smoke proves frontend calls only Marketplace and returned stream URLs remain Marketplace URLs.
5. Production external reachability smoke fails to reach Chat origin while private Marketplace call succeeds.

### Evidence Artifacts

- Focused test output for identity precedence and owner checks.
- Batch cross-owner regression proof.
- Run/SSE/WS missing-parent and cross-owner proof.
- Full pytest and release summary.
- Development cross-service smoke.
- Production private-network reachability evidence when promoted.

## Review Notes

- Open questions: none for Specification drafting.
- Accepted owner decisions:
  - Marketplace is the only production public authentication authority.
  - No service credential is added.
  - Development public exposure is accepted temporarily.
  - Production private networking is mandatory.
  - No direct or partially migrated Chat callers exist, so legacy Chat identity fallback and its environment switch are removed.
- Accepted compatibility decision:
  - Keep Chat ownership wallet-scoped and carry Marketplace account id separately.
- Rejected alternatives:
  - Make Chat validate Marketplace frontend JWTs: rejected because it duplicates the public auth boundary.
  - Add a second internal signed token: rejected as unnecessary for the approved production network.
  - Use `proxy_payload` alone for every route: rejected because GET/SSE/WS requests have no body; plain internal headers carry identity there.
  - Keep route-dependent wallet/user-id identity: rejected because it breaks consistent ownership.
- Self-review found no unresolved placeholder, ownership, compatibility, or environment-boundary contradiction; owner review is required before implementation planning.
