---
spec_id: SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001
module: hyperliquid_golden_answers
status: implemented
workflow_class: HARNESS-SPEC-FIRST-FEATURE
---

# Hyperliquid Golden Answers

## Specification

### Behavior

- `SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001-R1`: an approved Golden Case may declare
  one or more applicable Agent types. A run against another Agent type records
  the case as not applicable instead of treating it as a product defect.
- `SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001-R2`: facts that vary by Agent, including
  redemption policy and fee schedule, are evaluated against a sanitized target
  truth snapshot captured from the current Agent configuration. The approved
  ideal answer remains review evidence but cannot override the current Agent.
- `SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001-R3`: a case that declares a dynamic fact
  rule is blocked when its target truth is absent. Each dynamic rule supplies
  required fact groups and forbidden claims using the same deterministic
  matching contract as static hard facts. Approved missing-data alternatives
  recognize equivalent explicit wording such as not disclosed, not returned,
  unavailable, 未披露, 未返回, and no-current-data states. An explicit zero-state
  phrase such as no current/open positions is also accepted. An explicitly
  negated affirmative forbidden claim is not treated as an assertion, while forbidden
  claims that themselves describe a negative state retain exact-match behavior.
- `SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001-R4`: for a current-Agent detail-page turn,
  the answer chain obtains current Agent context before using fixed platform
  knowledge. Tool data wins on Agent identity, type, chain, creator, strategy
  disclosure, positions, activities, redemption configuration, and fees. A
  premature model answer is replaced by the required context call. Strategy,
  holding, position, and creator questions are current-Agent fact questions and
  must not be captured by assistant identity-introduction routing.
- `SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001-R5`: redemption answers state the current
  lock period and request/claim flow when configured. They state no lock or no
  window only when the current configuration explicitly supports that claim.
  A settlement-required boolean does not authorize explaining undisclosed
  position-closing, settlement mechanics, or settlement/claim ordering. The lock belongs to the returned
  redemption policy and must not be described as starting merely because a
  share was Minted; when the approved mechanism says the wait follows a Redeem
  request, the answer must not move that wait before the request.
- `SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001-R6`: fee answers enumerate the fee names
  and rates exposed for the current Agent. Mint/Redeem fees, Management Fee,
  and Profit Share remain distinct categories; absent fields are reported as
  unavailable rather than inferred. `rate_bps` is converted arithmetically and
  the typed `fee_type` is not renamed from UI wording. Fee cadence, collection
  mechanics, the status of unreturned fee types, and whether a management fee
  accrues or is waived during losses are not inferred.
- `SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001-R7`: first-person wording in an Agent
  question refers to the current page Agent. Viewer wallet activities or shares
  must not be substituted for Agent trades, positions, identity, or strategy.
- `SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001-R8`: missing strategy, report, position,
  or activity data produces a concise no-data answer. Generic market reasoning
  must not be presented as this Agent's undisclosed behavior.
- `SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001-R9`: when a model response contains tool
  calls, any co-emitted planning or search preamble is discarded. The user sees
  the post-tool answer only.
- `SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001-R10`: after typed current-Agent dynamic
  configuration is returned, unsupported fee cadence, collection, unreturned
  fee status, settlement mechanics, or claim-ordering assertions trigger at
  most two bounded internal output corrections. Invalid text and retry instructions are
  not emitted as the user-facing answer. Current-Agent final text is buffered
  until output validation accepts it; other turns retain incremental streaming.
  A post-retrieval planning sentence promising another search is not a completed
  answer and triggers the same bounded correction.
- `SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001-R12`: Mint-mechanism answers include
  proportional shares in the holder wallet, contract-governed pooled assets,
  executor/strategy use, and the creator's inability to dispose of pooled
  principal freely. They do not infer Agent purpose from its name or imply that
  optional creator reports are generated or published automatically.
- `SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001-R11`: approved platform-mechanism question
  families use current Agent context first and then fixed knowledge retrieval.
  The runtime enforces both calls when the model tries to answer early, while
  current typed configuration still overrides generic mechanism documentation.

### Invariants

- The supplied approved batch is scoped to Hyperliquid Agents and remains
  incremental; it is not interpreted as complete Marketplace business coverage.
- The evaluator does not silently rewrite product-owner source answers. Dynamic
  target truth uses explicit rule identifiers. When an approved static phrase
  conflicts with current dynamic configuration, the original ideal answer is
  retained as approval evidence while the conflicting hard group is replaced
  by the applicable dynamic rule.
- Target truth and reports reject real secrets and real-looking wallet or Agent
  addresses. No production credentials or private identity are persisted.
- Marketplace tools remain read-only, server-bound, and budgeted. No trading,
  Mint, Redeem, signature, wallet write, or service-token behavior is added.
- Existing language, input/output guardrail, provider-limit, stream/replay,
  owner, idempotency, and trusted Marketplace header contracts remain intact.

### Compatibility And Operations

- Approved cases without Agent-type or dynamic-rule fields retain v1 behavior.
- The report CLI accepts an optional target-truth JSON file. It is mandatory
  when selected cases declare dynamic rules or applicable Agent types.
- The target-truth CLI derives that sanitized evaluator input from Marketplace
  `ai-context`; it does not preserve Agent addresses or viewer context.
- Rollback is a code revert; no schema or data migration is required.
- Stable approved platform mechanisms missing from the canonical QnA corpus are
  released through a new versioned knowledge base and a blue-green default-KB
  switch; dynamic Agent values are never copied into that fixed corpus.

## Implementation Plan

1. Add failing tests for Agent-type applicability, required dynamic target
   truth, current-config fact/forbidden checks, and secret-safe source versions.
2. Add failing runtime tests for current-Agent context-first instructions,
   Q9/Q10 fact precedence, subject separation, missing-data behavior, and removal
   of co-emitted tool narration.
3. Implement the approved-case schema/report extension and document the target
   truth input contract.
4. Implement the minimal orchestration and prompt changes without hardcoding a
   Hyperliquid Agent id, lock duration, fee rate, or Golden question string.
5. Add a typed-context-scoped output validator with at most two correction attempts for
  unsupported dynamic claims that persisted after prompt instruction, including
  invented insurance, loss-absorbing, stop-loss, or loss-period fee mechanics.
6. Run focused tests, full change verification, release verification, and record
   closeout evidence below.

## Closeout Evidence

- The product-owner-approved Hyperliquid batch normalized to 36 bilingual cases
  across strategy/performance, Marketplace mechanism, portfolio/holders, and
  trust/safety coverage. The batch remains incremental rather than exhaustive.
- Live acceptance against Hyperliquid Agent 26 passed 36/36 deterministic hard
  checks and 36/36 semantic reviews, with zero release blockers, completion
  blockers, pending reviews, or identified semantic gaps. The final evidence is
  a 35-case unchanged full run plus the Q08 English targeted rerun after the
  only intervening runtime change raised the bounded output-correction ceiling.
- Stable approved Marketplace mechanisms were imported into a blue-green QnA
  V3 knowledge base: 18/18 documents ingested successfully, targeted retrieval
  returned the new Mint, copy-trading, loss-bearing, and holder-concentration
  material, and the prior V2 knowledge base remains available for rollback.
- The Marketplace current-Agent context endpoint was supplied by the upstream
  service and validated in the live flow. Dynamic Agent facts remained in typed
  context and were not copied into the fixed knowledge corpus.
- Runtime commit `18892530add5304ca777f3bf6c5fe562a76bd6b8` passed the project
  release gate, was deployed on DockerHost with QnA V3 selected, and returned
  healthy and ready probes. The remaining zero-position evaluator correction is
  behavior-neutral and is verified by the focused evaluator suite.
