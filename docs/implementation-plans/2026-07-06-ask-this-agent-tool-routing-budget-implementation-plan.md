# 2026-07-06 Ask this Agent Tool Routing And Budget Implementation Plan

## Plan Header

- Specification: `docs/specifications/2026-07-06-ask-this-agent-tool-routing-budget-specification.md`
- Spec ID: `SPEC-ASK-THIS-AGENT-TOOL-ROUTING-BUDGET-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Target branch/baseline: `codex/zai-glm52-dockerhost`
- Scope summary: Enforce service-owned tool routing and Marketplace per-turn budgets exposed by live DockerHost eval, plus clearer live replay timeout classification.
- Out of scope:
  - Public API changes, database migrations, PM-owned FAQ content, upstream Marketplace API changes, mandatory live eval in release gate.

## Change Steps

### Step 1: Tool Visibility Guard

- Files/modules:
  - `app/runtime/agent_factory.py`
  - `tests/test_tool_context_policy.py`
- Behavior change:
  - Hide `web_search` from default `ask_this_agent` turns through `PrepareTools`.
  - Preserve `turn_policy.tool_use == "none"` as the stronger all-tools-hidden path.
  - Leave other domain tools visible unless normal tool permissions deny them.
- Tests to add/update:
  - Verify default Ask this Agent tools do not include `web_search`.
  - Verify identity turn still hides every tool.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_tool_context_policy.py -q`

### Step 2: Marketplace Tool Budgets

- Files/modules:
  - `app/runtime/agent_factory.py`
  - `tests/test_agent_marketplace_tools.py`
- Behavior change:
  - Track per-run Marketplace tool call counts in `AgentDeps`.
  - Allow one external `marketplace_agent_context` call and one external `marketplace_agent_compute` call per run.
  - Remove each Marketplace tool from subsequent `PrepareTools` output after its per-run budget is spent.
  - Return `marketplace_tool_budget_exhausted` without calling the external client after the budget is spent.
- Tests to add/update:
  - Verify repeated context calls only hit the fake client once.
  - Verify repeated compute calls only hit the fake client once.
  - Verify Ask this Agent tool definitions no longer include Marketplace tools whose budgets are already spent.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_agent_marketplace_tools.py -q`

### Step 3: Live Replay Timeout Classification

- Files/modules:
  - `tests/chat_eval/live_runner.py`
  - `tests/test_chat_eval_closure.py`
- Behavior change:
  - Treat curl partial output after timeout as HTTP-like status `206` even when curl appended an HTTP status code.
  - Keep reports sanitized.
- Tests to add/update:
  - Verify partial stream reports become `stream_incomplete`.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_chat_eval_closure.py -q`

### Step 4: Review And Release Gate

- Files/modules:
  - All files above.
- Behavior change:
  - None beyond previous steps.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_tool_context_policy.py tests/test_agent_marketplace_tools.py tests/test_chat_eval_closure.py -q`
  - `AI_BOUNDARY_APPROVED=1 PYTHON=.venv/bin/python scripts/verify_release.sh`
- Rollback note:
  - Revert this spec/plan and the runtime/test helper changes. Public API callers are unaffected.

## Risk Controls

- Tool hiding is scoped to the default Ask this Agent behavior profile.
- Marketplace budgets prevent repeated external calls but still return structured information to the model.
- Spent-tool hiding prevents retry loops while preserving the fallback structured unavailable result if a stale or custom model path still invokes the tool.
- FAQ/product copy remains explicitly out of scope and listed as an external follow-up.
