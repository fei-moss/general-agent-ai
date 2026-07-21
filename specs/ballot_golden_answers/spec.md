---
spec_id: SPEC-BALLOT-GOLDEN-ANSWERS-001
module: ballot_golden_answers
status: implemented
workflow_class: HARNESS-SPEC-FIRST-FEATURE
---

# Ballot Golden Answers

## Specification

### Source And Scope

- Product-owner-approved source: `/Users/chris/Downloads/[Governance] Ask this Agent 问题预设.md`.
- Product domain label: Governance. Marketplace, Chat, and backend Agent type:
  `ballot`.
- The approved batch is incremental Golden Case evidence. It does not enumerate
  every ballot or Marketplace behavior.
- Q1 through Q18 retain their original Chinese and English questions and ideal
  answers. Source annotations remain audit evidence even where the latest owner
  instruction approves the batch.
- Q19 has no ideal answer in the supplied source. The owner explicitly excluded
  it from this release on 2026-07-21, so it is neither an approved case nor a
  pending-review, semantic-gap, or completion-blocker item.

### Behavior

- `SPEC-BALLOT-GOLDEN-ANSWERS-001-R1`: every case is applicable only to
  `ballot`. Runs against another Agent type are `not_applicable`, not product
  defects, hard failures, semantic gaps, or release blockers.
- `SPEC-BALLOT-GOLDEN-ANSWERS-001-R2`: approved source questions, ideal answers,
  language, risk, business area, approval evidence, and stable-versus-dynamic
  classification are preserved in the normalized cases without rewriting the
  product-owner source.
- `SPEC-BALLOT-GOLDEN-ANSWERS-001-R3`: stable ballot mechanisms come from a new
  bilingual, versioned Marketplace QnA corpus. The corpus explains the fixed
  mechanism and directs Agent-specific values to current typed context; it does
  not contain an Agent ID, address, target-specific value, or example answer
  hardcoded as runtime behavior.
- `SPEC-BALLOT-GOLDEN-ANSWERS-001-R4`: project identity, token symbols, fixed
  APY, reward source, payout denominations, display locations, proposal rules,
  voting rules, snapshot timing, vote mutability/cost, governance incentives,
  execution rules, redemption details, vote/redemption interaction, and
  concentration exceptions are dynamic facts. Current Marketplace `ai-context`
  wins over the static example, and missing data is reported as unavailable
  rather than invented.
- `SPEC-BALLOT-GOLDEN-ANSWERS-001-R5`: the target-truth artifact is derived from
  the target Agent's typed Marketplace `ai-context`, rejects a non-`ballot`
  target, and contains no Agent address, wallet, credential, report body, or
  unrelated response field.
- `SPEC-BALLOT-GOLDEN-ANSWERS-001-R6`: baseline acceptance covers transport and
  runtime completion, deterministic required facts, forbidden claims, semantic
  review, and Chinese/English consistency. Every failure is attributed to
  Prompt/answer composition, RAG/retrieval, tool/data, runtime/transport,
  product behavior, or evaluator behavior.
- `SPEC-BALLOT-GOLDEN-ANSWERS-001-R7`: completion requires zero hard failures,
  semantic gaps, pending reviews, release blockers, and completion blockers for
  all applicable ballot cases.
- `SPEC-BALLOT-GOLDEN-ANSWERS-001-R8`: the new QnA knowledge base is imported as
  a blue-green version, selected only after ingestion, semantic retrieval, live
  chat, and release acceptance pass. The previous knowledge base remains
  retained and selectable for rollback.

### Invariants

- Current-Agent values are never copied into the fixed QnA corpus or Prompt.
- Missing Marketplace data never becomes an affirmative product claim.
- No Mint, Redeem, vote, signature, wallet write, trade, or other mutating tool
  behavior is added.
- Existing identity, provider-limit, secret, owner, idempotency, streaming,
  replay, and trusted Marketplace-header boundaries remain unchanged.
- The implementation does not special-case a Golden question string, Agent ID,
  Agent address, or supplied demo answer.

### Release And Rollback

- Code rollback reverts the ballot-specific evaluator/runtime change if any.
- Data rollback switches `RAG_DEFAULT_KNOWLEDGE_BASE_ID` back to the retained
  previous knowledge base; neither knowledge base nor the managed PostgreSQL
  volume is deleted.
- Deployment uses the existing `chris-general-agent-ai-chat-prod` branch space,
  the pushed `Deploy` ref, and the repository DockerHost runbook.

## Implementation Plan

1. Add RED tests for the versioned governance source set, ballot-only case scope,
   stable/dynamic preservation, target-truth sanitization, and missing data.
2. Normalize the approved Q1-Q18 bilingual source into 36 ballot cases and
   record the owner-approved Q19 exclusion.
3. Add bilingual stable Governance/Ballot QnA sources, semantic paraphrases,
   representative chat cases, review evidence, and a versioned V5 seed.
4. Fetch the exact target Agent `ai-context`, run baseline, and attribute every
   failure before changing runtime, Prompt, tool, data, or evaluator behavior.
5. Implement only reproduced gaps, then rerun all ballot cases and the full QnA
   acceptance suite.
6. Run full pytest and `make verify-release`, push the feature branch, integrate
   into `Deploy`, deploy the normalized branch space, and verify Git/DockerHost
   SHA equality plus health, readiness, async Chat, SSE, and final run status.

## Closeout Evidence

- The owner-approved Q1-Q18 source was normalized losslessly into 36 applicable
  `ballot` cases: 18 Chinese and 18 English. Q19 remains explicitly excluded
  and creates no review or completion obligation.
- Current-Agent truth was derived from typed Marketplace `ai-context`. Stable
  mechanisms use the bilingual versioned QnA corpus; Agent-specific values and
  explicit `not_provided` states remain in typed current-Agent context.
- Final target acceptance passed all 36 applicable cases with zero hard
  failures, semantic gaps, pending reviews, release blockers, and completion
  blockers. Transport/runtime, required facts, forbidden claims, bilingual
  consistency, and human semantic review are included in the evidence.
- Blue-green QnA V5 acceptance passed: 20 documents and 184 chunks ingested,
  150/150 live retrieval cases passed with 131/150 Top-1 (87.33%), 150/150
  Promptfoo cases passed, and 20/20 live Chat cases passed. The prior production
  knowledge base remains retained for data-only rollback.
- Full `pytest`, Marketplace QnA acceptance validation, `verify-change`, and
  `verify-release` are required on the final integrated tree. DockerHost release
  evidence must additionally prove pushed `Deploy` ref/SHA equality, health,
  readiness, async Chat, SSE completion, and final run success.
