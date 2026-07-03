# 2026-07-03 Agent Identity Scope Guardrail Implementation Plan

Specification: `SPEC-AGENT-IDENTITY-SCOPE-GUARDRAIL-001`

Target branch/baseline: `codex/zai-glm52-dockerhost` at `d02007f339d05e113b843a7ee87f17d479fa4113`

Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`

## Scope Summary

Fix Ask this Agent self-introduction drift without fixed self-introduction templates by narrowing prompt tool-policy copy, strengthening model identity/presentation instructions, and expanding golden-case coverage.

## Out Of Scope

- Removing runtime calculator/clock/web-search tools.
- Changing Marketplace or current-Agent data contracts.
- Deployment.

## Change Steps

1. Tests and golden cases
   - Files/modules: `tests/test_chat_behavior_policy.py`, `tests/test_chat_behavior_eval.py`, `tests/test_orchestrator.py`, `tests/chat_eval/golden_cases.jsonl`, `tests/chat_eval/evaluator.py`.
   - Behavior change: encode self-introduction as `allow`, so it passes through the model; assert the prompt carries identity and readable-format constraints.
   - Data contract impact: none.
   - Tests to add/update: identity prompt allow decision, model-path orchestrator coverage, markdown-format prompt constraints, non-trigger for `这个 Agent 是做什么的?`, no identity fixed-template output replacement.
   - Verification command: `.venv/bin/python -m pytest tests/test_chat_behavior_policy.py tests/test_chat_behavior_eval.py tests/test_orchestrator.py -q`.
   - Rollback note: remove new cases and tests.

2. Runtime behavior policy
   - Files/modules: `app/runtime/chat_behavior.py`.
   - Behavior change: remove identity `respond` short-circuit and identity fixed-template output replacement; keep PRD identity and structured-format guidance in the system prompt.
   - Data contract impact: identity prompt run plan returns `action=allow`.
   - Tests to add/update: policy tests and eval validation.
   - Verification command: `.venv/bin/python -m pytest tests/test_chat_behavior_policy.py tests/test_chat_behavior_eval.py -q`.
   - Rollback note: revert enum/category additions and prompt changes.

3. Orchestrator handling
   - Files/modules: `app/runtime/orchestrator.py`.
   - Behavior change: identity prompts use the normal model execution path; existing deterministic refusal path remains only for safety guardrails.
   - Data contract impact: no API/event schema change; identity prompts use the normal plan metadata without a guardrail `respond` action.
   - Tests to add/update: orchestrator model-path test for identity prompts.
   - Verification command: `.venv/bin/python -m pytest tests/test_orchestrator.py -q`.
   - Rollback note: restore REFUSE-only short-circuit condition.

4. Verification and review
   - Files/modules: all changed files.
   - Behavior change: none.
   - Tests to add/update: any missing regression found during review.
   - Verification command: `.venv/bin/python -m pytest -q` and `AI_BOUNDARY_APPROVED=1 make verify-release`.

## Risk Controls

- Public contract risks: no request/response schema change.
- Money/accounting/security risks: no money logic touched.
- Migration/rebuild risks: none.
- Performance risks: only local pattern checks before model execution.
- Cost/latency risks: identity prompts now incur one model call by design.
- Deployment/test-branch risks: no deploy in this plan.
- Unrelated local changes to avoid: stage only identity guardrail spec, plan, runtime policy, orchestrator, docs/tests.

## Completion Criteria

- Spec matches implementation.
- Focused tests pass.
- Full tests and release gate pass.
- Code review finds no unresolved behavior drift.
