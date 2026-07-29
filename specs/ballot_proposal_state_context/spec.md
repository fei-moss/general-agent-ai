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
- Post-deploy verification (2026-07-29, Agent 64 live chat screenshot after
  R1-R5 were deployed to `chris-general-agent-ai-chat-prod`): the model
  correctly stopped claiming "no active proposal" (R2 confirmed working) but
  answered "The Ballot proposal tool is unavailable for this Agent at this
  time." Root cause confirmed via Marketplace backend source (MCI,
  2026-07-29): `MarketplaceAIClient` has a single `_base_url`, configured in
  this deployment to
  `MARKETPLACE_AI_BASE_URL=http://app.df-moss-site-agent-marketplace-dev.dockerhost:8081`
  — the dedicated **internal** listener that
  `docs/specifications/2026-07-23-backend-security-hardening-specification.md`
  states registers only `ai-context` and `ai-compute` ("The dedicated listener
  on port 8081 is the only surface that registers those two routes"). The R3
  proposals endpoint is registered on the separate **public** listener (port
  8080; confirmed reachable in R4's live smoke via the public HTTPS domain,
  never via the internal `:8081` host). `get_ballot_proposals` reuses the
  internal-only client, so every production call to it fails as
  `marketplace_unavailable`, which is exactly the "tool is unavailable"
  wording the model correctly reported instead of inventing an answer.
- Resolution decision (2026-07-29, owner call): fixed on the Marketplace side,
  not in this repository. `moss-site/agent_marketplace` already has an
  established precedent for exactly this situation —
  `docs/specifications/2026-07-27-internal-governance-sync-routes-specification.md`
  states "The same route shapes... remain available on Marketplace port
  `8081`" for other routes that originally existed only on the public
  listener. The owner will have the Marketplace backend team register
  `GET /api/v1/ballot/agents/{agent_id}/proposals` on the internal `8081`
  listener as well (mirroring that precedent), so `MarketplaceAIClient`'s
  existing single `_base_url` keeps working unchanged once that lands. This
  repository's `get_ballot_proposals` implementation is not changed for this
  issue; a second Chat-Server-side base URL was drafted and then reverted
  (uncommitted) in favor of this simpler, single-URL resolution.
- Marketplace-side fix landed and confirmed (2026-07-29, MCI): commit
  `570901666221ca2d5a503382c05855bdd2db080b` on `moss-site/agent_marketplace`
  registers `GET /api/v1/ballot/agents/{agent_id}/proposals` on the internal
  `8081` listener (`internal/transport/http/router.go`'s
  `NewInternalAIRouter`), confirmed by
  `internal/contract/internal_ai_listener_contract_test.go`. Per `API.md`
  (2026-07-29): "内网入口不解析或要求 JWT... 并在转发前清除 caller 的
  `Authorization`、`X-Marketplace-User-ID` 与 `X-Marketplace-Wallet`" — the
  internal registration is anonymous (`prepareAnonymousProxyRequest`, not
  `middleware.TrustedMarketplaceIdentity`) and strips any identity headers
  before forwarding. This confirms `get_ballot_proposals` sending no viewer
  headers is already correct, and `MarketplaceAIClient`'s single existing
  `_base_url` now reaches both `ai-context` and the proposals route — no
  second base URL is needed after all.
- Despite the above, re-verification against Agent 64 still returned "The
  Ballot proposal tool is unavailable for this Agent at this time." Root
  cause (2026-07-29): `extract_current_ballot_agent_id` resolves `agent_id`
  from server-owned `run_context`, but `run_context`'s only audited contract
  (`SPEC-MARKETPLACE-AI-INTERFACE-001-R1`) guarantees a contract *address*
  (`marketplace_agent.address`/`contract_address`, `agent.address`/
  `contract_address`, top-level `agent_address`/`contract_address`) — it was
  never specified to carry a ballot `agent_id`, and does not in production.
  Separately, Marketplace's `ai-context` response (`agent` object, per
  `internal/query/aicontext/service.go`) now includes
  `AgentID int64 json:"agent_id"` — the same field Chat Server's existing
  `marketplace_agent_context` tool already receives but does not read for
  this purpose. `extract_current_ballot_agent_id` must resolve `agent_id`
  from the `marketplace_agent_context` tool result (already fetched by Chat
  Server), not from `run_context`.

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
- `SPEC-BALLOT-PROPOSAL-STATE-CONTEXT-001-R6`: the ballot proposals turn
  resolves `agent_id` from the `marketplace_agent_context` tool's own result
  (`data.agent.agent_id`, as returned by Marketplace's `ai-context`), not from
  server-owned `run_context`. For a "current proposal" question, Chat Server
  calls `marketplace_agent_context` before `marketplace_ballot_proposals`
  when an `agent_id` has not already been resolved this turn, exactly as it
  already sequences other current-Agent tool dependencies. If `agent_id` is
  missing, non-numeric, or `ai-context` itself is unavailable, the proposals
  tool returns a structured `marketplace_unavailable` result (never a
  fabricated agent_id, and never silently falling back to an address-shaped
  value). `run_context`-based `agent_id` lookup, if any remains, is
  informational only and never required for this flow to succeed.

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
- R6 changes only how `agent_id` is sourced for the proposals turn (from the
  `marketplace_agent_context` result instead of `run_context`) and the
  within-turn tool call order; it does not change `marketplace_agent_context`
  itself, its budget, or non-ballot turns. Rollback is a code-and-test revert;
  no Marketplace-side change is required.

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
8. Add a RED test asserting that when `marketplace_ballot_proposals` runs
   after a `marketplace_agent_context` call whose result contains
   `data.agent.agent_id`, it calls `MarketplaceAIClient.get_ballot_proposals`
   with that resolved integer `agent_id` — and that when `agent_id` is
   absent, non-numeric, or `ai-context` itself failed, it returns a
   structured `marketplace_unavailable` result instead, per R6.
9. Change `agent_id` resolution for the ballot-proposals turn to read from
   `ctx.deps.marketplace_context_result` (the `marketplace_agent_context`
   tool's own result) instead of `run_context`, and adjust
   `_force_required_tool_call`/`_prepare_tools_for_turn` so
   `marketplace_agent_context` is called first when no `agent_id` has been
   resolved yet this turn, then `marketplace_ballot_proposals` runs with it.
   Make test 8 pass without changing `marketplace_agent_context` itself or
   non-ballot turns.
10. Run full `pytest`, `check_spec_contract.sh`, `verify-change`, and
    `verify-release` again on the integrated tree.
11. Redeploy `chris-general-agent-ai-chat-prod` on the `Deploy` ref and
    re-verify "is there a current proposal" against Agent 64 returns the
    real proposal data.

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
- Post-deploy follow-up #1 (2026-07-29, resolved on Marketplace side): R3's
  tool was initially blocked because `MARKETPLACE_AI_BASE_URL` only reached
  Marketplace's internal `ai-context`/`ai-compute`-only listener (port 8081)
  while the proposals endpoint lived on the public listener (port 8080). Per
  the owner's decision, the Marketplace backend team registered the route on
  the internal listener instead (commit `570901666221ca2d5a503382c05855bdd2db080b`,
  confirmed via MCI — see Source And Scope); no code in this repository
  changed for this follow-up, and a drafted second-base-URL fix was reverted
  uncommitted before landing.
- Post-deploy follow-up #2 (2026-07-29, local R6 implementation complete):
  after follow-up #1
  landed, re-verification against Agent 64 still returned "tool is
  unavailable." Root cause: this repository's `agent_id` resolution read
  `run_context`, whose only audited contract carries a contract address, not
  a ballot `agent_id` (see Source And Scope and R6). RED:
  `test_extract_current_ballot_agent_id_uses_marketplace_context_result_only`
  failed with `None != 64` for `data.agent.agent_id == "#64"`. GREEN:
  the resolver and proposal tool now read only the successful
  `marketplace_agent_context` result, the turn policy forces context before
  proposals while unresolved, and missing/non-numeric/unavailable context
  fails closed without using a conflicting `run_context.agent_id`.
- R6 verification (2026-07-29): 4 focused regression tests passed; the
  affected `test_agent_marketplace_tools.py`, `test_chat_behavior_eval.py`,
  and `test_marketplace_ai_client.py` suites passed (**148 passed**); full
  pytest passed (**675 passed, 1 skipped**); `scripts/check_spec_contract.sh`
  passed; and `verify-change` passed `change_scope`, `ai_boundaries`,
  `spec_registry`, and `legacy_spec_contract`. The sandbox's default asyncio
  loop did not wake worker-thread callbacks even in a minimal standard-library
  reproduction, so Agent tests ran under the already-installed `uvloop`;
  unchanged baseline Agent tests passed under the same workaround.
  `verify-release` stopped at its expected clean-tree precondition because
  this R6 change is intentionally uncommitted. Implementation Plan step 11
  remains pending until the owner commits the candidate to the `Deploy` ref
  and authorizes/executes the production redeploy and Agent 64 smoke.
- Independent re-verification (2026-07-29, this session, no uvloop
  workaround needed): full `pytest -q` with default asyncio — **738 passed,
  1 skipped**, exit code 0, no hang observed. `scripts/check_spec_contract.sh`
  passed. `verify-change` (`AI_BOUNDARY_APPROVAL_EVIDENCE=owner-request:
  approved in chat 2026-07-29, ballot proposal agent_id resolution fix (R6)`)
  passed all four gates; evidence in `.artifacts/change`. Code review of the
  diff (`extract_current_ballot_agent_id`, `marketplace_ballot_proposals`,
  `_force_required_tool_call`, `_prepare_tools_for_turn`) confirms it matches
  R6 exactly: `agent_id` is read only from a successful
  `marketplace_agent_context` result; a missing/non-numeric/unavailable
  result fails closed via the tool's own `CURRENT_BALLOT_AGENT_ID_MISSING`
  path rather than falling back to `run_context`.
