# Platform Mechanism Absorption Follow-Up Implementation Plan

Spec ID: `SPEC-PLATFORM-MECHANISM-ABSORPTION-002`
Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
Date: 2026-07-03

## Scope

Implement the second absorption batch: generic conversation anchors, masked run context plus tool permissions, behavior profiles, and an executable production deployment contract checker.

## Plan

1. Add red tests for `conversation_anchor` schema normalization, additive `ConversationAnchor` model constraints, repository lookup/bind behavior, and `/chat` anchor reuse.
2. Add red tests for runtime context masking, prompt instruction injection, and context-denied tool calls.
3. Add red tests for behavior profile registry selection, default compatibility, and run-plan profile metadata.
4. Add red tests for `production-deployment-contract.md`, `scripts/check_production_deployment_contract.py`, and `verify_release.sh` integration.
5. Implement anchor schema/model/repository/router wiring without changing existing conversation columns.
6. Implement `app/runtime/tool_context.py`, extend `AgentDeps`, and apply masking/tool denial inside `build_agent`.
7. Implement behavior profile registry in `app/runtime/chat_behavior.py`, wire `build_agent` and orchestrator plan metadata through server-owned settings.
8. Add the production deployment contract document and checker, then wire it into `scripts/verify_release.sh`.
9. Run focused tests, full pytest, Harness checks, and release verification.
10. Run a local code-review pass and fix actionable findings.

## Test Commands

```bash
.venv/bin/python -m pytest tests/test_conversation_anchors.py tests/test_tool_context_policy.py tests/test_chat_behavior_profiles.py tests/test_production_deployment_contract.py tests/test_chat_routing.py tests/test_agent_factory.py tests/test_orchestrator.py tests/test_production_readiness.py -q
.venv/bin/python -m pytest -q
AI_BOUNDARY_APPROVED=1 scripts/check_ai_boundaries.sh
scripts/check_spec_contract.sh
scripts/check_harness_workflows.sh
AI_BOUNDARY_APPROVED=1 PYTHON=.venv/bin/python scripts/verify_release.sh
```

## Loop Contract

- active_spec: `SPEC-PLATFORM-MECHANISM-ABSORPTION-002`
- active_plan: this implementation plan
- current_task: implement and verify each follow-up mechanism as a vertical slice
- stop_condition: focused tests, full pytest, Harness checks, code review, and release gate evidence are complete, or any blocker is explicit
- feedback_source: pytest, script checks, release summary, local code-review findings
- decision: continue until all four follow-up slices pass or a blocker is reached
