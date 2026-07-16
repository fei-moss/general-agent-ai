# Trusted Marketplace Chat Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Marketplace-injected account/wallet context mandatory and authoritative across Chat creation, conversations, runs, SSE, WebSocket, idempotency, anchors, rate limiting, and task execution in every environment.

**Architecture:** A focused identity module validates the two dedicated Marketplace headers with no user-facing Chat fallback or deployment mode switch. Middleware stores wallet owner plus account context in request state; `POST /chat` validates the reserved body identity against headers; repository and router owner checks fail closed before any route-specific side effect. The existing `/rag/*` internal-admin identity contract is independent and out of scope.

**Tech Stack:** Python 3.11+, FastAPI/Starlette, Pydantic v2 settings and schemas, SQLAlchemy async repositories, pytest/httpx, SSE/WebSocket routes, DockerHost Compose adapter, repository Harness scripts.

## Global Constraints

- Specification: `docs/specifications/2026-07-14-trusted-marketplace-chat-boundary-specification.md` (`SPEC-TRUSTED-MARKETPLACE-CHAT-BOUNDARY-001`).
- Parent contract: `SPEC-GLOBAL-AUTH-TRUSTED-CHAT-BOUNDARY-001` in `agent_marketplace`.
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`.
- Target branch/baseline: `chris/marketplace-trusted-chat-context` from `origin/codex/zai-glm52-dockerhost` at `176745bc036ada7f1951dd1170463b456ca248f4`.
- `X-Marketplace-User-ID` and `X-Marketplace-Wallet` are plain upstream context, not cryptographic proof.
- Development and production use the same mandatory Marketplace identity contract; production additionally requires private reachability and no public Chat ingress.
- No service JWT, HMAC, mTLS, encryption envelope, schema migration, frontend route change, or event-shape change.
- No direct or partially migrated user-facing Chat callers exist; URL `user_uuid`, raw Bearer/API-key identity, and WS query token compatibility are removed without a migration period.
- The independent `/rag/*` internal-admin authentication contract is unchanged.
- Existing Marketplace-created wallet owners remain readable without backfill.
- Owner validation happens before idempotency claim, provider preflight, capacity reservation, locks, persistence, queue dispatch, or realtime dispatch.
- AI boundary approval is recorded by the owner for runtime/API/config changes; verification still runs with `AI_BOUNDARY_APPROVED=1` where required.

---

### Task 1: Define the trusted identity resolver with red tests

**Files:**

- Create: `tests/test_marketplace_identity.py`
- Create: `app/api/identity.py`
- Modify: `tests/test_api_request_rate_limit.py`
- Modify: `tests/test_stream_replay.py`

**Interfaces:**

- Produces:

  ```python
  @dataclass(frozen=True, slots=True)
  class ResolvedIdentity:
      owner_id: str
      source: Literal["marketplace", "internal-admin"]
      marketplace_user_id: str | None = None
      marketplace_wallet: str | None = None

  class IdentityResolutionError(ValueError):
      status_code: int
      detail: str

  def resolve_http_identity(request: Request) -> ResolvedIdentity
  def resolve_websocket_identity(websocket: WebSocket) -> ResolvedIdentity
  ```

- [ ] **Step 1: Add pure resolver red tests**

  Test valid dedicated headers normalize wallet lowercase and return wallet as `owner_id`; conflicting `user_uuid`, Bearer, and API key do not affect ownership; one missing dedicated header, malformed values such as `marketplace:user:0`, over-64 user id, or malformed EVM wallet returns `422 MARKETPLACE_IDENTITY_INVALID`.

- [ ] **Step 2: Add mandatory-identity red tests**

  On `/chat`, `/conversations`, `/runs/*`, `/stream/*`, and `/ws/*`, missing dedicated headers returns `401 MARKETPLACE_IDENTITY_REQUIRED` even when `user_uuid`, Bearer, API key, or WS query token is present.

- [ ] **Step 3: Add rate-limit and WebSocket red tests**

  HTTP middleware must place the trusted wallet in `request.state.user_id`, causing the API limiter capture to receive the normalized wallet. WebSocket resolution must require dedicated headers and reject legacy-only connections.

- [ ] **Step 4: Run and verify RED**

  ```bash
  /Users/chris/AiProject/general-agent-ai/.venv/bin/python -m pytest -q tests/test_marketplace_identity.py tests/test_api_request_rate_limit.py tests/test_stream_replay.py
  ```

  Expected: import/behavior failures because the identity module and Marketplace mode do not yet exist.

### Task 2: Wire mandatory Marketplace identity into HTTP middleware, dependencies, and WebSocket

**Files:**

- Modify: `app/core/config.py`
- Modify: `app/api/identity.py`
- Modify: `app/api/middleware.py`
- Modify: `app/api/deps.py`
- Modify: `app/api/routers/stream.py`

**Interfaces:**

- Stores `request.state.user_id`, `request.state.user_id_source`, and `request.state.marketplace_identity` for dedicated-header requests.
- Removes `marketplace_identity_mode` and `MARKETPLACE_IDENTITY_MODE` because there is no alternate user-facing Chat mode.

- [ ] **Step 1: Implement strict Marketplace header parsing**

  Validate account id with `^marketplace:user:[1-9][0-9]*$` and wallet with `^0x[0-9a-fA-F]{40}$`; normalize wallet to lowercase. If either dedicated header is present, require and validate both rather than falling back.

- [ ] **Step 2: Remove user-facing Chat identity fallbacks**

  Delete URL `user_uuid`, Bearer, `X-API-Key`, and WebSocket query `token` from the user-facing Chat resolver. Preserve the separate `/rag/*` internal-admin authentication contract without treating it as Chat ownership.

- [ ] **Step 3: Wire middleware and dependency state**

  `AuthMiddleware` calls `resolve_http_identity(request)` for user-facing Chat routes, serializes `IdentityResolutionError` as `{"detail": detail}`, and writes the resolved owner/source/context to request state. `get_current_user` returns the middleware state owner; no unit-test or runtime Chat fallback derives owner from caller headers.

- [ ] **Step 4: Wire WebSocket through the same resolver**

  Call `resolve_websocket_identity` directly. Missing/invalid identity closes with code `1008` and a sanitized reason; valid Marketplace headers use wallet owner and ignore conflicting query identity.

- [ ] **Step 5: Verify GREEN**

  Run the Task 1 command. Expected: all identity, rate-limit, and WebSocket focused tests pass.

- [ ] **Step 6: Commit the identity boundary slice**

  ```bash
  git add app/core/config.py app/api/identity.py app/api/middleware.py app/api/deps.py app/api/routers/stream.py tests/test_marketplace_identity.py tests/test_api_request_rate_limit.py tests/test_stream_replay.py
  git commit -m "feat: accept trusted marketplace chat identity"
  ```

### Task 3: Validate reserved `proxy_payload` identity and protect prompt exposure

**Files:**

- Modify: `app/core/schemas.py`
- Modify: `app/api/routers/chat.py`
- Modify: `app/runtime/tool_context.py`
- Modify: `tests/test_marketplace_identity.py`
- Modify: `tests/test_chat_routing.py`
- Modify: `tests/test_tool_context_policy.py`

**Interfaces:**

- Produces a `MarketplaceIdentityIn` Pydantic model with `user_id` and `wallet_address`.
- Produces `ChatRequest.marketplace_identity` accessor returning validated reserved context or `None`.

- [ ] **Step 1: Add red endpoint tests for required, malformed, and mismatched body context**

  With dedicated headers, `POST /chat` requires:

  ```json
  {
    "proxy_payload": {
      "marketplace_identity": {
        "user_id": "marketplace:user:7",
        "wallet_address": "0x1111111111111111111111111111111111111111"
      },
      "user_address": "0x1111111111111111111111111111111111111111",
      "wallet_address": "0x1111111111111111111111111111111111111111"
    }
  }
  ```

  Missing/malformed reserved object returns `422 MARKETPLACE_IDENTITY_INVALID`; unequal header/body values or conflicting wallet aliases return `422 MARKETPLACE_IDENTITY_MISMATCH`; the repository override raises if touched.

- [ ] **Step 2: Add schema/accessor and router validation**

  Parse the nested object with Pydantic while leaving `proxy_payload` backward-compatible. At the top of `create_chat`, after message/stream validation and before request hashing, compare the normalized reserved identity and wallet aliases with `request.state.marketplace_identity`.

- [ ] **Step 3: Keep trusted raw context for tools but mask it from prompts/plans**

  Extend `mask_run_context` so keys `marketplace_identity`, `user_id`, `user_address`, and `wallet_address` do not expose raw values in prompt/plan metadata. The original `body.run_context` and task/realtime payload remain available to server-side tools.

- [ ] **Step 4: Verify RED then GREEN**

  ```bash
  /Users/chris/AiProject/general-agent-ai/.venv/bin/python -m pytest -q tests/test_marketplace_identity.py tests/test_chat_routing.py tests/test_tool_context_policy.py
  ```

- [ ] **Step 5: Commit the reserved-context slice**

  ```bash
  git add app/core/schemas.py app/api/routers/chat.py app/runtime/tool_context.py tests/test_marketplace_identity.py tests/test_chat_routing.py tests/test_tool_context_policy.py
  git commit -m "feat: validate marketplace chat runtime context"
  ```

### Task 4: Fail closed on every Chat owner boundary

**Files:**

- Create: `tests/test_chat_owner_authorization.py`
- Modify: `app/api/repos.py`
- Modify: `app/api/routers/chat.py`
- Modify: `app/api/routers/conversations.py`
- Modify: `app/api/routers/runs.py`
- Modify: `app/api/routers/stream.py`
- Modify: `tests/test_db_repositories.py`
- Modify: `tests/test_chat_routing.py`
- Modify: `tests/test_stream_replay.py`

**Interfaces:**

- Produces `ConversationOwnershipError` from repository-level conversation reuse.
- Produces one router helper that rejects existing null/different owners before side effects.

- [ ] **Step 1: Add a batch cross-owner red test**

  Call `create_chat` with `metadata.mode=batch`, `conversation_id` owned by another wallet, and fakes that raise if provider preflight, idempotency claim, `ensure_conversation`, task creation, commit, or dispatch occurs. Expected result is `403` before every fake side effect.

- [ ] **Step 2: Add repository defense-in-depth red tests**

  `Repos.ensure_conversation("conv", "wallet-b")` must raise `ConversationOwnershipError` when an existing row belongs to `wallet-a` or has `user_id=None`; same-owner reuse and new creation remain valid.

- [ ] **Step 3: Add conversation/run/stream fail-closed red tests**

  Conversation detail rejects null owner. Run status returns `404` when the parent conversation is missing and `403` for null/different owner. SSE/WS owner helper follows the same missing/null/different rules.

- [ ] **Step 4: Move owner validation before route selection side effects**

  At the start of `create_chat`, fetch an explicitly supplied conversation id and require `conversation.user_id == trusted_wallet`. Remove the realtime-only check. Catch `ConversationOwnershipError` around `ensure_conversation` and return the same `403` contract for race/defense cases.

- [ ] **Step 5: Tighten repository and read-route owner predicates**

  `ensure_conversation` checks owner before returning an existing row. Conversation `_assert_owner`, run status, and stream `_assert_run_owner` use strict equality; `None` is never treated as public ownership.

- [ ] **Step 6: Verify RED then GREEN**

  ```bash
  /Users/chris/AiProject/general-agent-ai/.venv/bin/python -m pytest -q tests/test_chat_owner_authorization.py tests/test_db_repositories.py tests/test_chat_routing.py tests/test_stream_replay.py
  ```

- [ ] **Step 7: Commit the owner-enforcement slice**

  ```bash
  git add app/api/repos.py app/api/routers/chat.py app/api/routers/conversations.py app/api/routers/runs.py app/api/routers/stream.py tests/test_chat_owner_authorization.py tests/test_db_repositories.py tests/test_chat_routing.py tests/test_stream_replay.py
  git commit -m "fix: enforce chat ownership across all routes"
  ```

### Task 5: Document the single identity contract and development/production network boundary

**Files:**

- Modify: `dockerhost/env.example`
- Modify: `dockerhost/compose.yaml`
- Modify: `docs/API.md`
- Modify: `docs/INTEGRATION_GUIDE.md`
- Modify: `docs/PRODUCTION_READINESS_RUNBOOK.md`
- Modify: applicable documentation/config contract tests under `tests/`

**Interfaces:**

- Removes `MARKETPLACE_IDENTITY_MODE` from settings and DockerHost configuration.
- Development may remain public but requires the same dedicated headers and is still not production security evidence.
- Production instructions require private reachability and no public Chat ingress.

- [ ] **Step 1: Add documentation/config contract red tests**

  Assert the env example, Compose, and runtime settings contain no identity mode switch; API docs describe dedicated headers/reserved payload and reject legacy direct Chat identity; no service credential is required; the production runbook requires private networking.

- [ ] **Step 2: Remove DockerHost identity-mode configuration**

  Remove `MARKETPLACE_IDENTITY_MODE` from `dockerhost/env.example` and `dockerhost/compose.yaml`; there is no alternative application identity behavior to configure.

- [ ] **Step 3: Update API and integration docs**

  Replace Marketplace `user_uuid` instructions with the two dedicated headers and reserved payload. Remove legacy direct Chat examples. State that plain headers are not proof on the current public development endpoint.

- [ ] **Step 4: Update production readiness instructions**

  Require private Chat reachability, no public domain/ingress, Marketplace-to-Chat positive smoke, and external negative reachability smoke. Do not add service-token, encryption, or identity-mode procedures.

- [ ] **Step 5: Verify GREEN**

  ```bash
  /Users/chris/AiProject/general-agent-ai/.venv/bin/python -m pytest -q tests/test_marketplace_identity.py tests/test_production_readiness.py tests/test_dockerhost_release_runbook_contract.py
  scripts/check_spec_contract.sh
  scripts/check_spec_registry.sh
  ```

- [ ] **Step 6: Commit the environment/documentation slice**

  ```bash
  git add dockerhost/env.example dockerhost/compose.yaml docs/API.md docs/INTEGRATION_GUIDE.md docs/PRODUCTION_READINESS_RUNBOOK.md tests
  git commit -m "docs: define marketplace chat deployment boundary"
  ```

### Task 6: Review, full verification, and cross-service readiness

**Files:**

- Review all files changed by Tasks 1-5.
- Do not stage `.env`, provider keys, DockerHost tokens, release artifacts, databases, or unrelated files.

**Review amendment:** Repository-owned user-facing Chat callers in `scripts/dockerhost_release.py`, `scripts/benchmark_realtime_ttft.py`, `tests/chat_eval/live_runner.py`, and the `Makefile` live-eval target must simulate Marketplace by sending both dedicated headers and matching reserved payload. `scripts/smoke_rag_pgvector.sh` remains on the independent `/rag/*` internal-admin contract.

- [ ] **Step 1: Review against both Specifications**

  Confirm trusted wallet consistency, header/body equality, mandatory identity in every environment, batch/realtime parity, strict null/missing owner behavior, prompt masking, frontend contract stability, and no service credential/schema migration.

- [ ] **Step 1a: Update repository-owned smoke, benchmark, and live-eval callers**

  Add script contract tests first. Replace user-facing Chat `X-API-Key`/Bearer identity with `X-Marketplace-User-ID`, `X-Marketplace-Wallet`, and a matching `proxy_payload.marketplace_identity`; use the same headers for run/SSE follow-up. Do not change the `/rag/*` smoke identity contract.

- [ ] **Step 2: Run focused and full verification**

  ```bash
  /Users/chris/AiProject/general-agent-ai/.venv/bin/python -m pytest -q tests/test_marketplace_identity.py tests/test_chat_owner_authorization.py tests/test_chat_routing.py tests/test_stream_replay.py tests/test_api_request_rate_limit.py tests/test_db_repositories.py tests/test_tool_context_policy.py
  /Users/chris/AiProject/general-agent-ai/.venv/bin/python -m pytest -q
  scripts/check_ai_boundaries.sh
  scripts/check_spec_contract.sh
  scripts/check_spec_registry.sh
  AI_BOUNDARY_APPROVED=1 PYTHON=/Users/chris/AiProject/general-agent-ai/.venv/bin/python scripts/verify_release.sh
  ```

- [ ] **Step 3: Inspect repository state and commit review fixes**

  `git diff --check`, `git status --short`, and `git diff origin/codex/zai-glm52-dockerhost...HEAD --stat` must show only task-related changes. Commit review fixes with a Conventional Commit message describing the actual fix.

- [ ] **Step 4: Prepare cross-service development smoke**

  The smoke uses a Marketplace-issued JWT against Marketplace only; verifies `202`, Marketplace stream URL, terminal SSE/run status, conversation list/detail, caller wallet override rejection, and no frontend-visible Chat origin. Direct development Chat reachability remains an explicitly accepted risk and is not production evidence.

## Risk Controls

- Public contract risks: Marketplace frontend shapes remain stable; only internal Chat caller identity changes.
- Security risks: the public development Chat URL can receive forged plain headers; this remains owner-approved only in development.
- Ownership risks: wallet is the persisted owner for compatibility; Marketplace account id is context only and does not merge multiple wallets.
- Migration/rebuild risks: none.
- Performance risks: header parsing is constant-time; owner checks reuse one existing conversation lookup and add no fan-out.
- Streaming risks: SSE/WS event/replay semantics remain unchanged; only pre-subscription identity/owner checks change.
- Provider risks: provider admission and settlement behavior remains fail-closed and out of scope.
- Unrelated local changes to avoid: all work remains in this isolated worktree and only task files are staged.

## Completion Criteria

- All local Specification acceptance criteria map to passing tests.
- Every new production behavior was preceded by an observed failing test.
- Dedicated Marketplace identity controls HTTP, SSE, WS, rate limiting, persistence, task payloads, idempotency, and anchors.
- Batch/realtime/forced/degraded paths enforce identical owner checks before side effects.
- Legacy user-facing Chat identity is rejected unconditionally and no mode switch remains.
- Existing wallet-owned conversations remain readable without migration.
- Focused tests, full pytest, AI boundary check, spec-contract check, Harness check, and release verification pass.
- Development docs explicitly accept public/no-credential risk; production docs require private/no-ingress topology.

## Loop Contract

- active_spec: `docs/specifications/2026-07-14-trusted-marketplace-chat-boundary-specification.md`
- active_plan: this document
- current_task: Task 1 - define the trusted identity resolver with red tests
- stop_condition: all acceptance criteria pass, full release harness is green, or an evidence-backed blocker is reported
- feedback_source: focused pytest, full pytest, AI boundary/spec/Harness checks, cross-service smoke
- decision: continue
