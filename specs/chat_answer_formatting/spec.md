---
spec_id: SPEC-CHAT-ANSWER-FORMATTING-001
module: chat_answer_formatting
status: implemented
workflow_class: HARNESS-SPEC-FIRST-FEATURE
---

# Chat Answer Formatting

## Specification

### Behavior

- `SPEC-CHAT-ANSWER-FORMATTING-001-R1`: the server behavior policy system prompt
  contains a compact Markdown table formatting constraint. Table cell text has
  no alignment padding before or after it, U+00A0 non-breaking spaces and
  U+3000 ideographic spaces are not used for alignment, separator rows use
  `|---|`, tables contain no more than four columns, and a standalone pure
  sequence-number column is not added.
- `SPEC-CHAT-ANSWER-FORMATTING-001-R2`: the constraint affects answer formatting
  only and does not change any field-value semantics. Ballot proposal `status`,
  `voting_starts_at`, and `voting_ends_at` values remain preserved verbatim as
  required by the existing specification.

### Invariants

- The constraint is injected through `build_system_prompt`; no runtime rewrite
  or regular-expression cleanup of model output is introduced.
- The streaming TOKEN contract, guardrail decisions, and language-consistency
  policy remain unchanged.

### Performance And Compatibility

- Public API paths and response schemas remain unchanged.
- `POLICY_VERSION` remains unchanged.

## Implementation Plan

1. Added failing assertions that the compact Markdown table instructions are
   injected into the system prompt.
2. Added the compact Markdown table constraint to the default behavior policy.
3. Recorded the focused pytest target and `make verify-change` as the final
   verification steps; their evidence remains pending below.

## Closeout Evidence

- Focused tests: RED proved the three new assertions failed against the previous
  policy (`build_system_prompt` output contained no compact-table instruction);
  GREEN passed `tests/test_chat_behavior_policy.py`,
  `tests/test_chat_behavior_profiles.py`, and `tests/test_chat_behavior_eval.py`.
- Full tests: `.venv/bin/python -m pytest -q` passed with one existing skip.
  Proxy environment variables must be unset for the run; a set `ALL_PROXY`
  makes unrelated `httpx` provider tests fail with a missing `socksio` package.
- Review or approval: `owner-request:chat-answer-table-formatting-2026-07-31`.
- Change gate: `AI_BOUNDARY_APPROVED=1
  AI_BOUNDARY_APPROVAL_EVIDENCE=owner-request:chat-answer-table-formatting-2026-07-31
  VERIFY_ACTIVE_SPEC_ID=SPEC-CHAT-ANSWER-FORMATTING-001
  VERIFY_COMPARE_REF=origin/Deploy make verify-change PY=.venv/bin/python`
  passed `change_scope`, `ai_boundaries`, `spec_registry`, and
  `legacy_spec_contract`.
- Release command: not run. This change was not committed, released, or
  deployed in the same session.
- Evidence path: `.artifacts/change`.
- Residual risk: the reported table layout defect is not root-caused yet. The
  raw Markdown of the failing answer and the frontend table DOM and computed
  style were both unavailable, so it is unconfirmed whether the padding
  originates from model output or from frontend rendering. This constraint is a
  prompt instruction only; model adherence is unverified against a real
  provider, and a frontend-side cause would not be fixed by it.
