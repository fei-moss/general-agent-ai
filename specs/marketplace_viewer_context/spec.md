---
spec_id: SPEC-MARKETPLACE-VIEWER-CONTEXT-001
module: marketplace_viewer_context
status: implemented
workflow_class: HARNESS-SPEC-FIRST-FEATURE
---

# Marketplace Viewer Context

## Specification

### Behavior

- `SPEC-MARKETPLACE-VIEWER-CONTEXT-001-R1`: after `POST /chat` validates the
  dedicated Marketplace headers and matching reserved `proxy_payload` identity,
  Chat Server constructs a typed `MarketplaceViewerContext` containing the
  Marketplace user id, normalized wallet, Agent run id, conversation id, and
  optional trace id. It cannot be constructed from model arguments, user text,
  or an unvalidated proxy payload.
- `SPEC-MARKETPLACE-VIEWER-CONTEXT-001-R2`: the typed viewer context travels as
  a separate server-only field through both realtime and Celery payloads,
  runners, tasks, orchestration, and `AgentDeps.marketplace_viewer_context`. It
  is never merged into model-visible `run_context`.
- `SPEC-MARKETPLACE-VIEWER-CONTEXT-001-R3`: `MarketplaceAIClient` accepts the
  trusted viewer context for both existing internal paths and sends exactly
  `X-Marketplace-User-ID`, `X-Marketplace-Wallet`, `X-Agent-Run-ID`,
  `X-Conversation-ID`, and `X-Trace-ID` when trace context is available. It
  never sends a frontend Marketplace JWT and callers cannot override identity
  headers.
- `SPEC-MARKETPLACE-VIEWER-CONTEXT-001-R4`: `marketplace_agent_context` and
  `marketplace_agent_compute` obtain the Agent address only from server-injected
  Agent context and viewer identity only from
  `ctx.deps.marketplace_viewer_context`. Model arguments expose neither Agent
  address nor wallet. Compute query status, reason, message, and availability
  remain unchanged.
- `SPEC-MARKETPLACE-VIEWER-CONTEXT-001-R5`: when trusted viewer context is
  absent, public Agent context may continue as an anonymous read-only GET.
  Wallet-scoped context or compute requests return a structured `unavailable`
  result and never fall back to body/query wallet fields. Static Agent answers
  remain free to avoid tool calls.

### Invariants

- `mask_run_context` remains the prompt/plan redaction boundary. Full wallet and
  Marketplace user id never enter system prompts, model requests, tool
  arguments, persisted plans, SSE/WebSocket events, logs, or public errors.
- Trusted header and reserved proxy identity mismatches fail closed before any
  conversation/run persistence or dispatch, preserving the existing ownership
  contract.
- Full viewer identity is only held in transient API/task/runtime memory and a
  Celery task payload required for execution; it is not copied into the queued
  task's model-visible `run_context` or the persisted run plan.
- Marketplace client timeout, invalid JSON, HTTP error, unsupported,
  insufficient-data, not-found, and unavailable semantics remain structured and
  sanitized; no missing value is replaced with an invented number.
- No trade, signature, wallet write, asset operation, service token, frontend
  JWT forwarding, schema migration, or ownership change is introduced.
- The Marketplace fix chain must expose the two existing AI paths on a private
  address and accept the five trusted headers under network-policy isolation.
  Cross-service/live acceptance remains blocked until that upstream change is
  deployed.

### Compatibility And Operations

- Existing callers without Marketplace viewer context retain anonymous public
  Agent-context behavior. Wallet-scoped data and compute fail closed.
- Existing routing, owner, idempotency, provider admission, streaming/replay,
  and tool-permission contracts remain unchanged.
- `MARKETPLACE_AI_BASE_URL` selects the private Marketplace address and defaults
  to empty so missing private-network configuration fails closed; public URL
  fallbacks are forbidden and no new credential setting is added.
- Rollback is a code revert; no data rollback is needed.

## Implementation Plan

1. Add failing tests for typed construction after header/body validation,
   mismatch rejection, model/plan masking, and realtime/batch payload survival.
2. Add failing client and tool tests for immutable trusted headers, anonymous
   GET, missing-viewer structured unavailability, server-owned Agent address,
   and preserved Marketplace result semantics.
3. Implement the typed context and API-to-runner/task-to-orchestrator propagation
   without changing `run_context` or public event shapes.
4. Inject trusted headers in `MarketplaceAIClient`, then wire both Agent tools to
   `AgentDeps.marketplace_viewer_context`.
5. Run focused tests, full pytest, boundary/spec checks, review, and
   `scripts/verify_release.sh`; record evidence below. Run live page smoke only
   after the Marketplace fix chain is deployed.

## Closeout Evidence

- Focused tests: 139 identity, client, tool, routing, realtime/batch, owner,
  idempotency, stream, and tool-permission tests passed.
- Full pytest: passed with one existing skip.
- Review or approval: owner request in this task approves the listed runtime,
  API, and task changes; final review found and fixed execution-binding and
  nested tool-argument override gaps, with no unresolved high-impact finding.
- Change verification: `VERIFY_COMPARE_REF=HEAD scripts/verify_change.sh`
  passed; evidence is under `.artifacts/change/`.
- Release command: `VERIFY_COMPARE_REF=fd679be^ scripts/verify_release.sh`
  passed on the clean final feature candidate.
- Evidence path: `.artifacts/change/` and `.artifacts/release/`.
- Residual risk: the Marketplace fix branch is committed through `f653c50` and
  its clean release evidence reports `release_ready=true`, but it is not yet
  merged, pushed, deployed, or connected to Chat through the production private
  network. Cross-service HTTP 200 and production page acceptance therefore
  cannot yet be claimed.
