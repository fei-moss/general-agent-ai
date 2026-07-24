---
spec_id: SPEC-MARKETPLACE-AGENT-PROTOCOL-CREATED-AT-001
module: marketplace_agent_protocol_created_at
status: implemented
workflow_class: HARNESS-SPEC-FIRST-FEATURE
---

# Marketplace Agent Protocol Creation Time

## Specification

### Behavior

- `SPEC-MARKETPLACE-AGENT-PROTOCOL-CREATED-AT-001-R1`: when a user explicitly
  asks when the current Agent was created, Chat Server calls
  `marketplace_agent_context` exactly once and answers from
  `agent.deployed_at`. This value is the timestamp of the block containing the
  Factory `AgentCreated` protocol event and is described as the Agent's protocol
  creation time with an explicit timezone.
- `SPEC-MARKETPLACE-AGENT-PROTOCOL-CREATED-AT-001-R2`: the Marketplace client
  preserves the RFC3339 `agent.deployed_at` value exactly as returned by
  `GET /api/v1/agents/{address}/ai-context`; Chat Server does not rename, copy,
  calculate, or enrich it from another source.
- `SPEC-MARKETPLACE-AGENT-PROTOCOL-CREATED-AT-001-R3`: if `agent.deployed_at` is
  missing, empty, or unavailable, the answer states that the protocol creation
  time is not currently provided. It does not guess a time or direct the user
  to an Explorer.
- `SPEC-MARKETPLACE-AGENT-PROTOCOL-CREATED-AT-001-R4`: a scoped bilingual
  current-Agent output validator rejects creation-time answers that use an
  Explorer, first transaction, contract creation time, Marketplace listing
  time, Metadata time, or Agent Tool creation time as a substitute. It also
  rejects omission of a returned `deployed_at` value or its protocol-event
  meaning and requests an internal rewrite without exposing the correction.
- `SPEC-MARKETPLACE-AGENT-PROTOCOL-CREATED-AT-001-R5`: creation-time turns do
  not call `marketplace_agent_compute` or `search_knowledge`. Questions about
  how to verify a contract that do not explicitly ask for the current Agent's
  creation time remain outside the scoped creation-time validator.

### Invariants

- The current Agent address and viewer identity remain server-owned. Tool
  parameters do not accept Agent, wallet, user, or identity values.
- Marketplace requests retain the existing trusted identity headers and do not
  add `Authorization` or `MARKETPLACE_AI_SERVICE_TOKEN`.
- No RPC, block Explorer, third-party lookup, database, migration, public Chat
  API schema, RAG corpus, trading, signing, funds, or private-key behavior is
  introduced.
- Protocol creation time is not contract first-transaction time, inferred
  contract-deployment time, Marketplace ingestion/listing time, Metadata time,
  or Agent Tool strategy-creation time.

### Compatibility

- The raw Marketplace `ai-context` wrapper and existing tool parameter Schema
  remain unchanged.
- Current-Agent context-first routing, one-call budgets, identity headers,
  streaming buffering, and non-creation question behavior remain compatible.
- Rollback is a code-and-test revert; no data rollback or Marketplace change is
  required.

## Implementation Plan

1. Add failing tests for exact client passthrough, model-visible tool semantics,
   bilingual current-Agent creation-time answers, internal rewrite, and missing
   data without fallback.
2. Add bilingual Golden Cases and register `deployed_at` in the data-consistency
   contract without changing unrelated thresholds.
3. Extend only the existing context tool description, current-Agent turn
   instruction, and scoped output validator in `app/runtime/agent_factory.py`.
4. Run focused tests, full pytest, spec/change gates, review the final diff, and
   record only observed closeout evidence below.

## Closeout Evidence

- RED test evidence: before runtime changes, the focused suite failed only the
  new tool-description, turn-instruction, and Explorer-draft rewrite tests;
  exact failures were
  `test_marketplace_context_tool_description_defines_protocol_creation_time`,
  `test_agent_injects_current_agent_fact_precedence_instruction`, and
  `test_protocol_creation_time_explorer_draft_is_rewritten_internally`.
- Focused tests: the six required Marketplace client, Agent tool, turn-policy,
  behavior-policy, chat-eval, and eval-closure files passed 226 tests; the
  legacy spec contract passed for 29 specifications and 29 plans.
- Full tests: the implementation pass and clean release gate completed all 630
  collected tests with one existing skip.
- Review or approval: the owner's 2026-07-24 task explicitly authorizes the
  requested runtime, tests, and specification changes.
- Change verification: `VERIFY_COMPARE_REF=origin/Deploy make verify-change`
  passed change-scope, AI-boundary, spec-registry, and legacy-contract gates
  with owner approval evidence.
- Review: final contract and diff review found no open behavioral, API, auth,
  identity, retry, streaming, or scope defect.
- Release command: with
  `TASK_VENV="$(dirname "$(git rev-parse --path-format=absolute
  --git-common-dir)")/.venv"`, clean
  `AI_BOUNDARY_APPROVED=1
  AI_BOUNDARY_APPROVAL_EVIDENCE=owner-request:marketplace-agent-protocol-created-at-2026-07-24
  VERIFY_ACTIVE_SPEC_ID=SPEC-MARKETPLACE-AGENT-PROTOCOL-CREATED-AT-001
  VERIFY_COMPARE_REF=origin/Deploy make verify-release VENV="$TASK_VENV"` passed
  every Harness and project gate with `release_ready=true`.
- Chat eval: dataset V2 scorecard passed 45 allowed cases with zero forbidden
  claim hits, 100% safety and data-faithfulness pass rates, and 0.8571 trait hit
  rate.
- DockerHost acceptance: the first real-Agent replay returned the exact
  `deployed_at` value and explicit timezone but omitted the Factory
  `AgentCreated` block-time meaning. A preserved RED regression reproduced the
  gap, the scoped output validator was tightened, and the six-file focused
  suite passed again before the corrected candidate was released.
- Evidence path: `.artifacts/change/` and `.artifacts/release/`; the final
  amended candidate is reverified to bind evidence to its final SHA.
- Residual risk: Marketplace must independently provide the contracted
  `agent.deployed_at` field; when it does not, Chat Server intentionally reports
  that protocol creation time is not provided.
