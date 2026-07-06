# 2026-07-06 Ask this Agent Tool Routing And Budget Specification

## Context

- Spec ID: `SPEC-ASK-THIS-AGENT-TOOL-ROUTING-BUDGET-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Source request: Live DockerHost chat eval showed weak behavior on Marketplace data, platform FAQ, and financial-boundary allowed cases. Fix what is service-owned and list upstream/product gaps separately.
- Target baseline: current `codex/zai-glm52-dockerhost` branch after Marketplace AI integration and chat eval closure work.
- Problem:
  - Ask this Agent turns can still expose and call `web_search`, even though the product scope is the current Agent detail page and fixed platform mechanisms.
  - Marketplace compute/context tools can be called repeatedly in one turn, causing long model/tool loops and incomplete stream output.
  - Live replay currently labels some timed-out partial streams as `run_completed_missing` instead of a clearer partial stream failure.
- Non-goals:
  - Do not add or change public HTTP routes.
  - Do not make live replay mandatory in release gates.
  - Do not invent PM-owned FAQ answers for Profit Share, Paused Redeem, or fee settlement.
  - Do not change the upstream Marketplace AI endpoint contract beyond documenting observed `chain_id` behavior as an external follow-up.

## Product Semantics

- Ask this Agent is scoped to the current Agent detail page, Marketplace AI context/compute results, and fixed platform mechanism knowledge.
- External web search is not a user-facing capability for this product surface and should not be visible to the model by default.
- Marketplace tools are read-only data access helpers. A single turn should not repeat the same expensive Marketplace tool indefinitely.
- Ask this Agent model requests should not allow provider-side parallel tool calls, because parallel Marketplace calls can create noisy duplicate tool events before per-run budget visibility can be refreshed.
- If a provider still emits multiple Marketplace tool calls in one model response, the runtime collapses duplicate Marketplace calls before tool execution; duplicate `marketplace_agent_compute` calls are merged into one call by combining unique `queries`.
- If a Marketplace tool budget is exhausted before a tool invocation can be prepared, that tool is hidden from later model requests in the same run so the model can answer from already-returned data instead of retrying a spent tool.
- If a Marketplace tool is invoked after its budget is exhausted through any fallback path, the model receives a structured unavailable result and should answer from already-returned data or state that the data is temporarily unavailable.
- Stream/live-eval failure reports should distinguish partial stream timeout from a completed run with empty final content.

## API / Interface Contract

- No public API request or response contract changes.
- Internal runtime tool visibility changes:
  - `web_search` is hidden from the default `ask_this_agent` behavior profile. Any future external-search opt-in requires a separate server-owned policy/spec.
  - `turn_policy.tool_use == "none"` still hides all tools.
- Internal Marketplace budget changes:
  - Agent model settings set `parallel_tool_calls` to `false` by default.
  - Duplicate Marketplace tool calls within a single model response are filtered before execution; duplicate compute calls preserve distinct query objects by merging them into the first compute call.
  - `marketplace_agent_context` may make at most one external call per run.
  - `marketplace_agent_compute` may make at most one external call per run.
  - Once either Marketplace tool has reached its per-run limit, that tool is omitted from subsequent Pydantic AI tool definitions prepared for the same run.
  - Exceeding the budget returns a structured Marketplace unavailable payload with reason `marketplace_tool_budget_exhausted`.
- Live replay report changes:
  - Curl timeout with partial SSE data is classified as stream status `206`, allowing reports to mark `stream_incomplete`.

## Data / Schema / Projection Impact

- No database schema, migration, projection, or cache changes.
- No persisted data format changes.

## Architecture

- Modules/files expected to change:
  - `app/runtime/agent_factory.py`
  - `tests/chat_eval/live_runner.py`
  - `tests/test_tool_context_policy.py`
  - `tests/test_agent_marketplace_tools.py`
  - `tests/test_chat_eval_closure.py`
- Runtime responsibilities:
  - Model request settings prevent provider-side parallel tool call fan-out for this Agent.
  - An `after_model_request` hook removes duplicate Marketplace tool call parts before Pydantic AI emits tool execution events.
  - Tool visibility is enforced through Pydantic AI `PrepareTools`, not only through prompt text.
  - Marketplace per-run budgets are enforced in tool implementations before external client calls.
  - Marketplace spent-tool hiding is enforced through the same `PrepareTools` path, using `AgentDeps.tool_call_counts` as the source of truth.
  - Live replay error classification remains test-only and does not affect production runtime.

## Acceptance Criteria

- `web_search` is absent from the function tools exposed to default Ask this Agent turns.
- Identity turns continue to hide all tools.
- Calculator/clock/search_knowledge/Marketplace tools remain available when applicable.
- Model settings disable parallel tool calls by default so the model must observe one tool result before requesting the next tool.
- Same-response duplicate Marketplace compute calls are merged into a single external call with combined unique queries.
- Repeated Marketplace context or compute calls in the same run do not call the external client more than once.
- Marketplace context or compute tools are no longer visible to the model after their per-run budget has been spent.
- Budget-exhausted Marketplace calls return a structured unavailable result that can be answered from by the model.
- Live replay marks curl timeout partial streams as incomplete.
- Focused tests and release verification pass.

## External Follow-Ups

- PM/product must supply authoritative FAQ answers for fee settlement, Paused Redeem, and other fixed platform mechanism questions.
- Upstream Marketplace AI owner should confirm whether `chain_id` is unsupported, optional, or mapped differently for the provided public Agent address.
- If external web search is ever required, product should define a server-owned opt-in policy and citation rules.
