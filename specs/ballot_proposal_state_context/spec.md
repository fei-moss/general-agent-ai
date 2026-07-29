---
spec_id: SPEC-BALLOT-PROPOSAL-STATE-CONTEXT-001
module: ballot_proposal_state_context
status: implemented
workflow_class: HARNESS-SPEC-FIRST-FEATURE
---

# Ballot Proposal State Context

## Specification

### Source And Scope

- Incident evidence: a live Ballot Agent (`am-alpha.moss.site/agent/ballot/64`,
  contract `0xe0b0...cbdc`) shows `4 Active` proposals on its Marketplace
  governance page, including "Agent 64 latest snapshot voting test" with
  status `In Progress` and `Ends: 2026-08-04`. The same Agent's "Ask this
  Agent" Chat answered "there is no active proposal" and listed
  `proposal_display_location`, `proposal_creation_rule`, `proposal_threshold`,
  and `snapshot_timing_rule` as `Not provided`.
- Root cause reproduced against current code, not inferred: calling
  `annotate_ballot_context_availability` with a synthetic Marketplace
  `ai-context` payload that includes real values for every
  `BALLOT_DYNAMIC_CONTEXT_FIELDS` key still returns `not_provided` for every
  field except `project_name` and `project_token`, because the function's
  `direct` mapping only wires those two fields to `agent.name` /
  `agent.accept_token_symbol`; every other field falls through to a
  hardcoded `(None, "marketplace_agent_context")` default regardless of what
  Marketplace actually returned.
- A second, independent gap was found while tracing the same incident:
  `_BALLOT_ABSENCE_INFERENCE_PATTERNS` in `app/runtime/agent_factory.py` only
  matches "no fixed apy / governance rewards / voting rewards" phrasing. It
  does not match "there is no active proposal" or "没有进行中的提案", so that
  overclaim is not caught by `_unsupported_ballot_claims` and reaches the
  user unchanged.
- A third gap, now confirmed against Marketplace backend source (not
  inferred): `BALLOT_DYNAMIC_CONTEXT_FIELDS` only models proposal *rules*
  (creation rule, threshold, display location, snapshot timing, execution
  rule, etc.). `GET /api/v1/agents/{address}/ai-context` structurally cannot
  carry a live proposal *instance* (id, title, status, end time, tallies),
  because Marketplace's own architecture keeps that data out of the Agent
  context path by design: `moss-site/agent_marketplace`'s
  `docs/specifications/2026-07-10-ballot-agent-gateway-proxy-specification.md`
  states "No Ballot proposal, vote, nonce, signature, or rendering business
  logic in Marketplace." Live proposal instances are owned by a separate
  service, `moss-site/marketplace-ballot-agent` (its own `governance_proposals`
  Postgres table and `model.Proposal` type), and are already exposed publicly
  through Marketplace's gateway at
  `GET /api/v1/ballot/agents/{agent_id}/proposals` (auth policy
  `marketplace_optional`: anonymous callers get the same response, so no
  trusted viewer identity is required). Confirmed response fields include
  `id`, `title`, `status` (a `ProposalStatus` enum, e.g. `draft`),
  `voting_starts_at`, and `voting_ends_at` (RFC3339) — this is the same data
  rendered as "Agent 64 latest snapshot voting test / In Progress / Ends
  2026-08-04" in the incident screenshot. Chat Server's
  `marketplace_agent_context` tool never calls this endpoint today; it only
  calls `ai-context`. Adding a proposal-instance field inside
  `annotate_ballot_context_availability`/`ai-context` is therefore the wrong
  fix — the correct fix is a new read-only tool call against the existing
  public proposals endpoint.
- This spec is scoped to Ballot (`agent_type == "ballot"`) Agents only. It
  does not change Hyperliquid or other Agent-type behavior.

### Behavior

- `SPEC-BALLOT-PROPOSAL-STATE-CONTEXT-001-R1`: `annotate_ballot_context_availability`
  reads every key in `BALLOT_DYNAMIC_CONTEXT_FIELDS` from the Marketplace
  `agent` payload (or the correct nested location confirmed by R4's live
  smoke) when present, and marks it `available` with the returned value. A
  field is `not_provided` only when Marketplace genuinely omits it, never as
  a hardcoded default that ignores a returned value.
- `SPEC-BALLOT-PROPOSAL-STATE-CONTEXT-001-R2`: the ballot output validator
  rejects an answer that asserts no proposal currently exists, is active, or
  is open (in Chinese or English, e.g. "there is no active proposal",
  "no proposal is currently open", "没有进行中的提案", "当前没有提案") whenever
  proposal-instance state was not itself returned as an explicit `false`/empty
  result from Marketplace. The required wording is that current proposal
  instance data is not provided or not returned; the model must not convert
  "the rule fields are not provided" into "no proposal exists".
- `SPEC-BALLOT-PROPOSAL-STATE-CONTEXT-001-R3`: for "is there a current
  proposal" style questions on a Ballot Agent, Chat Server calls a new
  read-only tool against the existing public
  `GET /api/v1/ballot/agents/{agent_id}/proposals` endpoint (Marketplace
  gateway, `marketplace_optional` auth, no viewer identity required) and
  surfaces the returned `title`, `status`, `voting_starts_at`, and
  `voting_ends_at` verbatim, with no renaming, aggregation, or invented
  field. This is separate from and does not read through
  `ballot_governance`/`ai-context`. If the call returns no rows, is
  unavailable, or errors, the answer states plainly that current proposal
  instance data is not returned and points to the proposal page, and does
  not claim a proposal does or does not exist.
- `SPEC-BALLOT-PROPOSAL-STATE-CONTEXT-001-R4`: confirmed via Marketplace
  backend source (`moss-site/agent_marketplace` and
  `moss-site/marketplace-ballot-agent`, verified 2026-07-29): the
  proposal-instance endpoint, its auth policy, and its response fields exist
  exactly as described in Source And Scope. Before implementation, a
  read-only live/dev smoke call against
  `GET /api/v1/ballot/agents/{agent_id}/proposals` for Agent 64 records the
  exact live response bytes as a schema-drift check (confirming the
  implementation matches source, not discovering whether the field exists).
  This smoke evidence is required in Closeout Evidence before R3 is marked
  implemented.
- `SPEC-BALLOT-PROPOSAL-STATE-CONTEXT-001-R5`: every other approved Ballot
  golden answer, dynamic-fact rule, and missing-data wording from
  `specs/ballot_golden_answers/spec.md` remains unchanged. This spec only
  fixes how already-approved dynamic fields are populated and validated; it
  does not rewrite the approved Q1-Q18 source or its ideal answers.

### Invariants

- No Agent ID, address, proposal ID, or example value is hardcoded into
  runtime code, Prompt, or corpus as a stand-in for real Marketplace data.
- A `not_provided`/`not returned` field never becomes an affirmative "does not
  exist" or "no active X" product claim; this applies uniformly across all
  `BALLOT_DYNAMIC_CONTEXT_FIELDS`, not only the two mechanisms already guarded
  (`redeem_during_vote_rule`, `voting_power_rule`).
- No Mint, Redeem, vote, signature, wallet write, trade, or other mutating
  tool behavior is added. The new R3 tool is a read-only `GET` against an
  already-public endpoint; it accepts no user- or model-supplied Agent
  address, mirroring the existing `marketplace_agent_context` resolution
  pattern.
- Existing identity, provider-limit, secret, owner, idempotency, streaming,
  replay, and trusted Marketplace-header boundaries remain unchanged.

### Compatibility

- The raw Marketplace `ai-context` wrapper, tool parameter Schema, and
  non-ballot Agent-type behavior remain unchanged.
- `ballot_governance` keeps its existing `{availability, value, source}` shape;
  R1 changes how each field's `value` is resolved, not the shape consumers
  read.
- Rollback is a code-and-test revert; no data migration or Marketplace-side
  change is required for R1/R2. R3 rollback additionally removes the new
  read-only proposal-instance tool call; the public
  `/api/v1/ballot/agents/{agent_id}/proposals` endpoint itself is owned by
  `moss-site/marketplace-ballot-agent` and is unaffected by this repository's
  rollback.

## Implementation Plan

1. Add a RED test to `tests/test_marketplace_ai_client.py` asserting that when
   the Marketplace `agent` payload includes a real value for a
   `BALLOT_DYNAMIC_CONTEXT_FIELDS` key other than `project_name`/`project_token`
   (e.g. `proposal_creation_rule`, `voting_power_rule`), the annotated
   `ballot_governance` entry is `available` with that value. This test must
   fail against current code before any implementation change.
2. Add a RED test to `tests/test_agent_marketplace_tools.py` asserting
   `_unsupported_ballot_claims` flags "there is no active proposal" and
   "没有进行中的提案" style output, independent of the two existing
   `redeem_during_vote_rule`/`voting_power_rule` checks.
3. Run a read-only dev/live smoke against
   `GET /api/v1/ballot/agents/{agent_id}/proposals` for Agent 64 (or an
   equivalent Ballot Agent with a confirmed active proposal) and record the
   response bytes as Closeout Evidence, without persisting raw Marketplace
   payloads into runtime state. This validates the implementation matches
   the source-confirmed contract; it is not a discovery step.
4. Generalize `annotate_ballot_context_availability` so every
   `BALLOT_DYNAMIC_CONTEXT_FIELDS` key is resolved from the confirmed
   Marketplace location instead of only `project_name`/`project_token`, then
   make test 1 pass.
5. Extend the ballot absence-inference guard to cover proposal-existence
   overclaims per R2, then make test 2 pass.
6. Add a new read-only Marketplace client method and Agent tool (mirroring
   `MarketplaceAIClient.get_agent_context`'s address resolution and error
   handling) that calls `GET /api/v1/ballot/agents/{agent_id}/proposals` and
   returns `title`/`status`/`voting_starts_at`/`voting_ends_at` per R3, then
   extend the Ballot golden Q&A corpus with a matching "is there a current
   proposal" case using this tool's output.
7. Run full `pytest`, the Ballot golden-case acceptance suite, `verify-change`,
   and `verify-release` on the integrated tree before any deployment.

## Closeout Evidence

- Focused tests: RED was recorded before implementation for the ignored
  `agent.proposal_creation_rule` / `agent.voting_power_rule` values, bilingual
  proposal-absence claims, missing Agent-ID resolver and proposal client, and
  the absent golden case (5 failures). Two additional RED cases reproduced
  omitted returned proposal fields and vague empty-result wording. GREEN
  evidence covers 10 new focused tests plus the affected client, Agent-tool,
  tool-policy, and chat-behavior suites (164 passed).
- Ballot golden acceptance: `tests/test_approved_golden_case_workflow.py` plus
  `tests/test_chat_behavior_eval.py` passed (118 tests).
- Source evidence (R4):
  confirmed 2026-07-29 via read-only code search (MCI) against
  `moss-site/agent_marketplace` (repository_id `1269703257`) and
  `moss-site/marketplace-ballot-agent` (repository_id `1287784519`,
  `feature/governance-agent-foundation`). Key evidence: `agent_marketplace`
  `docs/specifications/2026-07-10-ballot-agent-gateway-proxy-specification.md`
  (no Ballot business logic in Marketplace's own context path),
  `internal/transport/http/openapi.yaml` (`/ballot/agents/{agent_id}/proposals`
  route), `internal/contract/auth_openapi_contract_test.go` /
  `docs/specifications/2026-07-15-ballot-consumer-trusted-marketplace-identity-specification.md`
  (`marketplace_optional` auth); `marketplace-ballot-agent`
  `internal/model/types.go` (`Proposal.ID/Title/Status/VotingEndsAt`),
  `internal/httpapi/router.go`, `docs/frontend-integration-api.md` (live
  example payload with `voting_ends_at`).
- Live smoke evidence (R4, Implementation Plan step 3): confirmed 2026-07-29
  via read-only
  `GET https://app-df-moss-site-agent-marketplace-dev.dkhost.vixmk-yo.org/api/v1/ballot/agents/64/proposals?limit=10&offset=0`
  (no auth header sent, `marketplace_optional` policy honored, `HTTP 200`).
  Response shape is `{agent_config, items[], pagination}`. All 4 `items` have
  `status: "open"` (matches the incident screenshot's "4 Active"); item
  `id 37` has `title: "Agent 64 最新快照投票测试"` /
  `display_config.i18n["en-US"].title: "Agent 64 latest snapshot voting
  test"`, `voting_ends_at: "2026-08-04T09:48:58.282Z"` (matches "Ends:
  2026-08-04"), and `vote_summary` (`total_vote_count: 1`,
  `options: [{choice: "for", vote_count: 1, voting_power:
  "2000000000000000000000"}, ...]`) matches the screenshot's 100% Pass /
  2,000 votes. Confirms Source And Scope and R3/R4 exactly; no further
  discovery needed before implementation.
- Review or approval: implementation was explicitly requested by the repo
  owner in chat on 2026-07-29 ("是的一起做了 直到问题修复"); recorded as
  `AI_BOUNDARY_APPROVAL_EVIDENCE=owner-request:approved in chat 2026-07-29,
  ballot proposal state context fix` for the `app/` approval-required paths.
- Release command: rebuilt `.venv` with system Python 3.12 (the originally
  provided `.venv`/Python 3.14 could not build `sqlalchemy`'s `greenlet`
  dependency) and installed the full `requirements.txt`. With that venv:
  `PYTHONPATH=. .venv/bin/python -m pytest -q` — **738 passed, 1 skipped**,
  exit code 0 (sandbox `ALL_PROXY`/`HTTPS_PROXY` env vars caused 11 unrelated
  provider-model collection failures until unset; confirmed environment-only,
  not a regression). `scripts/check_spec_contract.sh` passed.
  `VERIFY_COMPARE_REF=13b324d AI_BOUNDARY_APPROVED=1
  AI_BOUNDARY_APPROVAL_EVIDENCE="owner-request:..." bash scripts/verify_change.sh`
  passed all four gates (`change_scope`, `ai_boundaries`, `spec_registry`,
  `legacy_spec_contract`); evidence written to `.artifacts/change`.
  `scripts/verify_release.sh` was attempted and failed at
  `release_context_before` because release verification requires a clean
  (committed) working tree — this repo's changes are intentionally left
  uncommitted pending the owner's explicit commit instruction, so
  `verify-release` has not been run to completion.
- Evidence path: `tests/test_marketplace_ai_client.py`,
  `tests/test_agent_marketplace_tools.py`,
  `tests/test_chat_behavior_eval.py`, `tests/chat_eval/golden_cases.jsonl`,
  `.artifacts/change/` (verify-change evidence).
- Residual risk: implementation, full test suite, `check_spec_contract`, and
  `verify-change` are all green. The only outstanding gate is
  `verify-release`, which requires committing the change first; that is a
  separate, explicit decision left to the owner and not taken here.
