# 2026-06-24 Streaming Output Guardrail Implementation Plan

## Plan Header

- Specification: `docs/specifications/2026-06-24-streaming-output-guardrail-specification.md`
- Spec ID: `SPEC-STREAMING-OUTPUT-GUARDRAIL-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Target branch/baseline: `codex/zai-glm52-dockerhost` at `781ee3be73500cdfde29833a4b99262b693c8a3c`
- Scope summary: Restore realtime token emission for safe assistant output while preserving deterministic output guardrail protection through a bounded sliding tail window.
- Out of scope:
  - Public API/event/schema changes, provider limiter changes, external moderation/judge services, load-test harness implementation, Async Runner service split.

## Change Steps

### Step 1: Add Failing Tests First

- Files/modules:
  - `tests/test_chat_behavior_policy.py`
  - `tests/test_orchestrator.py`
- Behavior change:
  - Express the required streaming behavior before runtime code changes.
- Data contract impact:
  - None.
- Tests to add/update:
  - `StreamingOutputGuardrail` releases safe prefixes while retaining a tail window.
  - `StreamingOutputGuardrail` blocks a leak split across provider chunks.
  - Orchestrator emits a safe `TOKEN` before the model stream is allowed to finish.
  - Orchestrator never emits split leaked text and persists the same safe text it emits.
  - Existing output-guardrail replacement and TTFT metric tests remain green.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_policy.py tests/test_orchestrator.py -q`
- Rollback or compatibility note:
  - Tests should fail before implementation because current code emits `TOKEN` only after `_run_agent()` returns.

### Step 2: Add Streaming Output Guardrail Helper

- Files/modules:
  - `app/runtime/chat_behavior.py`
- Behavior change:
  - Extract output leak patterns used by `evaluate_assistant_answer()`.
  - Add a helper that:
    - stores only a bounded pending tail plus current provider chunk;
    - releases safe prefixes once they cannot become part of a future deterministic leak pattern;
    - detects high-confidence leaks across chunk boundaries;
    - finalizes remaining safe tail;
    - exposes the emitted safe answer for persistence.
- Data contract impact:
  - None.
- Tests to add/update:
  - `tests/test_chat_behavior_policy.py`.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_policy.py -q`
- Rollback or compatibility note:
  - Helper is local and dependency-free; reverting restores full-answer review behavior once orchestrator changes are reverted.

### Step 3: Stream Safe Chunks From Orchestrator

- Files/modules:
  - `app/runtime/orchestrator.py`
- Behavior change:
  - Move safe `TOKEN` emission into the model text stream loop.
  - Feed raw model deltas through the streaming output guardrail before `TokenAggregator`.
  - Preserve `LLM_GENERATING`, tool events, provider quota acquisition/settlement, fallback answer, persistence, and terminal event behavior.
  - Build the final assistant answer from emitted safe chunks.
  - Remove or narrow the post-generation `_apply_output_guardrail()`/`_emit_token_chunks()` batch path so it no longer delays allowed output until completion.
- Data contract impact:
  - None; `TOKEN.data.token` and `RUN_COMPLETED.data.content` stay compatible.
- Tests to add/update:
  - `tests/test_orchestrator.py`.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_orchestrator.py -q`
- Rollback or compatibility note:
  - Revert this file plus helper/tests to return to full buffering.

### Step 4: Fix Documentation Drift

- Files/modules:
  - `README.md`
  - `docs/API.md`
  - `app/api/routers/chat.py`
  - `docs/specifications/2026-06-24-chat-behavior-policy-and-guardrails-specification.md`
  - `docs/implementation-plans/2026-06-24-chat-behavior-policy-and-guardrails-implementation-plan.md`
- Behavior change:
  - Clarify that realtime chat runs through the resident async RealtimeRunner, while Celery remains for batch/slow tasks.
  - Mark the old full-buffering guardrail tradeoff as superseded by `SPEC-STREAMING-OUTPUT-GUARDRAIL-001`.
- Data contract impact:
  - None.
- Tests to add/update:
  - None.
- Verification command:
  - `scripts/check_spec_contract.sh`
  - `scripts/check_harness_workflows.sh`
- Rollback or compatibility note:
  - Documentation-only changes; no runtime effect.

### Step 5: Harness Checks and Review

- Files/modules:
  - All changed docs/tests/runtime/API files.
- Behavior change:
  - None beyond implementation.
- Data contract impact:
  - None.
- Tests to add/update:
  - Fix only failures tied to `SPEC-STREAMING-OUTPUT-GUARDRAIL-001`.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_policy.py tests/test_orchestrator.py -q`
  - `scripts/check_ai_boundaries.sh`
  - `scripts/check_spec_contract.sh`
  - `scripts/check_harness_workflows.sh`
  - `scripts/verify_release.sh`
- Rollback or compatibility note:
  - If `scripts/verify_release.sh` fails for environment-only reasons, preserve focused test and harness output and report the blocker.

## Risk Controls

- Public contract risks:
  - Keep event names, payload shapes, route behavior, and status codes unchanged.
  - Preserve `RUN_COMPLETED.data.content` as the final safe assistant text.
- Money/accounting/security risks:
  - Do not weaken input guardrails, provider admission, usage settlement, or secret redaction.
  - Do not emit high-confidence hidden-instruction or secret leak text in `TOKEN`.
- Migration/rebuild risks:
  - None.
- Performance risks:
  - Tail-window scanning must stay local and bounded.
  - No external moderation call in the stream loop.
  - Focused test must prove token emission occurs before model completion.
- Deployment/test-branch risks:
  - Runtime/API paths require owner approval under `.ai-boundaries.yml`.
  - Release readiness still requires `scripts/verify_release.sh` or an explicit blocker.
- Unrelated local changes to avoid:
  - Do not stage `.artifacts/`, `__pycache__`, local runbooks, secrets, or unrelated DockerHost/Z.AI work.

## Completion Criteria

- Specification still matches implementation.
- Focused tests pass and include a pre-completion token emission assertion.
- AI boundary, spec contract, and harness workflow checks pass.
- Release verification passes or a concrete blocker is reported.
- Code review loop finds no unresolved streaming, guardrail, contract, or secret-hygiene issue.
