# 2026-06-24 Agent Positioning Policy Tuning Implementation Plan

## Plan Header

- Specification: `docs/specifications/2026-06-24-agent-positioning-policy-tuning-specification.md`
- Spec ID: `SPEC-AGENT-POSITIONING-POLICY-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Target branch/baseline: `codex/zai-glm52-dockerhost` at `0a5660d5dc9bab3bd644ac3dc2b496d1d20e72d7`
- Scope summary: Convert the product Lark positioning document for `交易类Agent--Ask this Agent` into v2 default policy text, deterministic personal-wallet-data refusal, and doc-derived golden cases with answer-level judge coverage.
- Out of scope:
  - Public API changes, DB migrations, UI changes, real RAG corpus work, wallet integration, external judge services, and production legal copy finalization.

## Change Steps

### Step 1: Add Product-Positioning Golden Cases

- Files/modules:
  - `tests/chat_eval/golden_cases.jsonl`
  - `tests/chat_eval/judge.py`
  - `tests/chat_eval/evaluator.py`
  - `tests/test_chat_behavior_eval.py`
- Behavior change:
  - Add cases from Lark sections 2 to 6 covering allowed data sources, business-scope refusals, style constraints, private-key scam refusal, and personal-wallet-data refusal.
  - Add deterministic judge answers for allowed cases so answer-trait scoring remains meaningful.
  - Count the new personal-wallet-data guardrail category.
- Data contract impact:
  - None. Test fixtures only.
- Tests to add/update:
  - Coverage assertion for the new category.
  - Policy variant label update to v2.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_eval.py -q`
- Rollback or compatibility note:
  - Remove added fixture rows and judge entries if the product positioning is rolled back.

### Step 2: Update Default Behavior Policy

- Files/modules:
  - `app/runtime/chat_behavior.py`
  - `tests/test_chat_behavior_policy.py`
- Behavior change:
  - Increment `POLICY_VERSION` to `SPEC-CHAT-BEHAVIOR-POLICY-001/v2`.
  - Replace the generic assistant identity with Ask this Agent detail-page positioning.
  - Add source boundaries, Live Activities "转述 + 总结", risk language, style rules, no external market/news lookup, and business-refusal boundaries.
- Data contract impact:
  - Existing run-plan `policy_version` remains an additive string; no schema change.
- Tests to add/update:
  - Prompt contract assertions for Ask this Agent identity, source boundary, risk disclaimer, and no investment-adviser positioning.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_policy.py tests/test_agent_factory.py -q`
- Rollback or compatibility note:
  - Revert policy text and version to v1 if product wants generic assistant behavior again.

### Step 3: Add Deterministic Personal Wallet Data Refusal

- Files/modules:
  - `app/runtime/chat_behavior.py`
  - `tests/test_chat_behavior_policy.py`
- Behavior change:
  - Add `personal_wallet_data` guardrail category.
  - Refuse high-confidence requests for the user's wallet balance, holdings, or Agent shares because the Agent has no permission to inspect user private data.
- Data contract impact:
  - Additive run-plan guardrail category string only.
- Tests to add/update:
  - Direct unit test for "我的钱包里有多少余额?".
  - Golden case for personal wallet balance.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_policy.py tests/test_chat_behavior_eval.py -q`
- Rollback or compatibility note:
  - Category is additive and can be removed with matching fixture changes.

### Step 4: Focused and Release Verification

- Files/modules:
  - All changed docs/runtime/tests files.
- Behavior change:
  - None beyond implementation.
- Data contract impact:
  - None.
- Tests to add/update:
  - Fix only regressions caused by this spec.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_policy.py tests/test_chat_behavior_eval.py tests/test_agent_factory.py tests/test_orchestrator.py -q`
  - `PYTHON=.venv/bin/python make test`
  - `PYTHON=.venv/bin/python AI_BOUNDARY_APPROVED=1 make verify-release`
- Rollback or compatibility note:
  - If release gate fails for environment-only reasons, report exact blocker and focused-test evidence.

### Step 5: Review and Closeout

- Files/modules:
  - `git diff` and changed files.
- Behavior change:
  - None.
- Data contract impact:
  - None.
- Tests to add/update:
  - Any missing test found in review.
- Verification command:
  - Repeat focused tests after fixes.
- Rollback or compatibility note:
  - Do not stage unrelated files or generated artifacts.

## Risk Controls

- Public contract risks:
  - No route, request, response, status, event, or schema change.
- Money/accounting/security risks:
  - Advice and prediction are constrained by prompt/golden cases.
  - Direct real-money operations and private-key exfiltration remain deterministic refusals.
  - Personal wallet data is refused deterministically.
- Migration/rebuild risks:
  - None.
- Performance risks:
  - Only local string checks and larger static prompt text are added.
- Deployment/test-branch risks:
  - Runtime path requires `AI_BOUNDARY_APPROVED=1` for release verification per `.ai-boundaries.yml`.
- Unrelated local changes to avoid:
  - Do not stage `.artifacts/`, browser screenshots, local runbooks, credentials, or unrelated branch work.

## Completion Criteria

- All planned files changed or explicitly deferred.
- Specification still matches implementation.
- Focused tests pass.
- `make test` passes.
- `make verify-release` passes with `AI_BOUNDARY_APPROVED=1`.
- Review finds no unresolved behavior, safety, or test coverage issue.
