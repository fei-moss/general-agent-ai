# 2026-07-03 Agent Identity Scope Guardrail Implementation Plan

Specification: `SPEC-AGENT-IDENTITY-SCOPE-GUARDRAIL-001`

Target branch/baseline: `codex/zai-glm52-dockerhost` at `d02007f339d05e113b843a7ee87f17d479fa4113`

Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`

## Scope Summary

Fix Ask this Agent self-introduction drift by adding deterministic identity responses, narrowing prompt tool-policy copy, adding output drift detection, improving answer presentation, and expanding golden-case coverage.

## Out Of Scope

- Removing runtime calculator/clock/web-search tools.
- Changing Marketplace or current-Agent data contracts.
- Deployment.

## Change Steps

1. Tests and golden cases
   - Files/modules: `tests/test_chat_behavior_policy.py`, `tests/test_chat_behavior_eval.py`, `tests/test_orchestrator.py`, `tests/chat_eval/golden_cases.jsonl`, `tests/chat_eval/evaluator.py`.
   - Behavior change: encode self-introduction as deterministic `respond`, not model/tool execution; assert the response uses readable Markdown sections and bullets.
   - Data contract impact: none.
   - Tests to add/update: identity prompt response, markdown structure, non-trigger for `这个 Agent 是做什么的?`, output identity drift replacement, orchestrator no-tool short-circuit.
   - Verification command: `.venv/bin/python -m pytest tests/test_chat_behavior_policy.py tests/test_chat_behavior_eval.py tests/test_orchestrator.py -q`.
   - Rollback note: remove new cases and tests.

2. Runtime behavior policy
   - Files/modules: `app/runtime/chat_behavior.py`.
   - Behavior change: add `GuardrailAction.RESPOND`, `identity_introduction`/`identity_drift` categories, identity prompt matcher, localized scoped response, high-confidence generic identity output guardrail, and structured-format prompt guidance.
   - Data contract impact: run plan guardrail action may be `respond`.
   - Tests to add/update: policy tests and eval validation.
   - Verification command: `.venv/bin/python -m pytest tests/test_chat_behavior_policy.py tests/test_chat_behavior_eval.py -q`.
   - Rollback note: revert enum/category additions and prompt changes.

3. Orchestrator handling
   - Files/modules: `app/runtime/orchestrator.py`.
   - Behavior change: deterministic `respond` action uses the existing safe-answer path and skips model/tool execution.
   - Data contract impact: no API/event schema change; plan metadata gets `action=respond`.
   - Tests to add/update: orchestrator short-circuit test.
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
- Deployment/test-branch risks: no deploy in this plan.
- Unrelated local changes to avoid: stage only identity guardrail spec, plan, runtime policy, orchestrator, docs/tests.

## Completion Criteria

- Spec matches implementation.
- Focused tests pass.
- Full tests and release gate pass.
- Code review finds no unresolved behavior drift.
