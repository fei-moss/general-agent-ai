---
spec_id: SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001
module: hyperliquid_golden_answers
status: draft
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
  matching contract as static hard facts.
- `SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001-R4`: for a current-Agent detail-page turn,
  the answer chain obtains current Agent context before using fixed platform
  knowledge. Tool data wins on Agent identity, type, chain, creator, strategy
  disclosure, positions, activities, redemption configuration, and fees.
- `SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001-R5`: redemption answers state the current
  lock period and request/claim flow when configured. They state no lock or no
  window only when the current configuration explicitly supports that claim.
  A settlement-required boolean does not authorize explaining undisclosed
  position-closing or settlement mechanics.
- `SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001-R6`: fee answers enumerate the fee names
  and rates exposed for the current Agent. Mint/Redeem fees, Management Fee,
  and Profit Share remain distinct categories; absent fields are reported as
  unavailable rather than inferred. `rate_bps` is converted arithmetically and
  the typed `fee_type` is not renamed from UI wording. Fee cadence, collection
  mechanics, and the status of unreturned fee types are not inferred.
- `SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001-R7`: first-person wording in an Agent
  question refers to the current page Agent. Viewer wallet activities or shares
  must not be substituted for Agent trades, positions, identity, or strategy.
- `SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001-R8`: missing strategy, report, position,
  or activity data produces a concise no-data answer. Generic market reasoning
  must not be presented as this Agent's undisclosed behavior.
- `SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001-R9`: when a model response contains tool
  calls, any co-emitted planning or search preamble is discarded. The user sees
  the post-tool answer only.

### Invariants

- The supplied approved batch is scoped to Hyperliquid Agents and remains
  incremental; it is not interpreted as complete Marketplace business coverage.
- The evaluator does not silently rewrite product-owner source answers. Dynamic
  target truth is additive evidence with explicit rule identifiers.
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
5. Run focused tests, full change verification, release verification, and record
   closeout evidence below.

## Closeout Evidence

Pending implementation and verification.
