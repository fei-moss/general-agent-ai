# Marketplace AI Interface Integration Implementation Plan

Spec ID: `SPEC-MARKETPLACE-AI-INTERFACE-001`
Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
Date: 2026-07-03

## Scope

Wire Marketplace's centralized read-only Agent data interfaces into the runtime Agent as context-bound tools.

## Plan

1. Add red tests for current Agent address extraction, Marketplace GET/POST request construction, and sanitized failure results.
2. Add red tests for Agent tool invocation, missing current Agent address, and context-denied Marketplace tools.
3. Implement `app/runtime/marketplace_ai.py` with address resolution and an async HTTP client.
4. Add Marketplace settings and DockerHost/env examples.
5. Extend `RuntimeDeps` and `AgentDeps` to carry the Marketplace client.
6. Register `marketplace_agent_context` and `marketplace_agent_compute` tools in `build_agent`.
7. Update Ask this Agent behavior policy and orchestrator tool-plan metadata.
8. Run focused tests, full pytest, Harness checks, release verification, and a local code-review pass.

## Test Commands

```bash
/Users/chris/AiProject/general-agent-ai/.venv/bin/python -m pytest tests/test_marketplace_ai_client.py tests/test_agent_marketplace_tools.py tests/test_agent_factory.py tests/test_tool_context_policy.py tests/test_orchestrator.py -q
/Users/chris/AiProject/general-agent-ai/.venv/bin/python -m pytest -q
AI_BOUNDARY_APPROVED=1 scripts/check_ai_boundaries.sh
scripts/check_spec_contract.sh
scripts/check_spec_registry.sh
AI_BOUNDARY_APPROVED=1 PYTHON=/Users/chris/AiProject/general-agent-ai/.venv/bin/python scripts/verify_release.sh
```

## Loop Contract

- active_spec: `SPEC-MARKETPLACE-AI-INTERFACE-001`
- active_plan: this implementation plan
- current_task: add Marketplace client and Agent tool wiring
- stop_condition: focused tests, full pytest, Harness checks, local code review, and release gate pass
- feedback_source: pytest, script checks, live dev smoke evidence, and release summary
- decision: continue until the interface is integrated or a missing product context blocks accurate implementation
