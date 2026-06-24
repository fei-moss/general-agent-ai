# 2026-06-24 Chat Behavior Eval Framework Implementation Plan

## Plan Header

- Specification: `docs/specifications/2026-06-24-chat-behavior-eval-framework-specification.md`
- Spec ID: `SPEC-CHAT-BEHAVIOR-EVAL-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Target branch/baseline: current `codex/zai-glm52-dockerhost` worktree with `SPEC-CHAT-BEHAVIOR-POLICY-001/v1`
- Scope summary: Add deterministic, data-driven chat behavior golden cases under `tests/chat_eval/`, plus a local validator and pytest coverage so future chat tuning can be expressed as machine-readable cases.
- Out of scope:
  - Runtime behavior changes, DB changes, public API changes, external LLM judge, Promptfoo execution, provider calls, Langfuse integration.

## Change Steps

### Step 1: Add Golden Case Fixture

- Files/modules:
  - `tests/chat_eval/golden_cases.jsonl`
- Behavior change:
  - Adds machine-readable examples for allow/refuse, false positives, RAG requirements, output safety, answer traits, and forbidden claims.
- Data contract impact:
  - None; test fixture only.
- Tests to add/update:
  - New `tests/test_chat_behavior_eval.py`.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_eval.py -q`
- Rollback or compatibility note:
  - Remove fixture if reverted; no migration.

### Step 2: Add Local Eval Loader And Validator

- Files/modules:
  - `tests/chat_eval/evaluator.py`
- Behavior change:
  - Loads JSONL, validates case shape, checks unique ids, enum values, fixture coverage, and secret hygiene.
- Data contract impact:
  - None.
- Tests to add/update:
  - `tests/test_chat_behavior_eval.py` validates loader and fixture.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_eval.py -q`
- Rollback or compatibility note:
  - Test helper only.

### Step 3: Add Pytest Contract Coverage

- Files/modules:
  - `tests/test_chat_behavior_eval.py`
- Behavior change:
  - Verifies golden cases against `evaluate_user_message()` and `evaluate_assistant_answer()`.
  - Enforces coverage gates for future tuning.
- Data contract impact:
  - None.
- Tests to add/update:
  - New test file only.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_eval.py tests/test_chat_behavior_policy.py -q`
- Rollback or compatibility note:
  - Test-only rollback.

### Step 4: Harness Verification And Review

- Files/modules:
  - All new spec/plan/test fixture files.
- Behavior change:
  - None beyond deterministic test framework.
- Data contract impact:
  - None.
- Tests to add/update:
  - Fix only failures related to eval framework.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_eval.py tests/test_chat_behavior_policy.py -q`
  - `PYTHON=.venv/bin/python make test`
  - `PYTHON=.venv/bin/python AI_BOUNDARY_APPROVED=1 make verify-release`
- Rollback or compatibility note:
  - Existing runtime and API behavior should remain unchanged.

## Risk Controls

- Public contract risks:
  - No API or runtime changes.
- Money/accounting/security risks:
  - Fixture validator rejects real-looking secrets and keeps real-money operation cases as policy examples only.
- Migration/rebuild risks:
  - None.
- Performance risks:
  - Local JSONL parsing and deterministic function calls only.
- Deployment/test-branch risks:
  - Release gate remains authoritative.
- Unrelated local changes to avoid:
  - Do not stage `.artifacts/`, `__pycache__`, private local runbooks, or unrelated runtime changes.

## Completion Criteria

- Spec and implementation plan exist and declare `Workflow Class: HARNESS-SPEC-FIRST-FEATURE`.
- Golden cases fixture has at least 10 validated cases and required coverage axes.
- Focused eval tests pass.
- Existing behavior policy tests pass.
- Full pytest passes.
- Harness release gate passes or reports a concrete blocker.
- Review finds no unresolved schema, secret-hygiene, or compatibility issue.
