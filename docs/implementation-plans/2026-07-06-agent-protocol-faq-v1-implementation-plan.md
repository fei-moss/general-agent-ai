# 2026-07-06 Agent Protocol FAQ V1 Implementation Plan

## Plan Header

- Specification: `docs/specifications/2026-07-06-agent-protocol-faq-v1-specification.md`
- Spec ID: `SPEC-AGENT-PROTOCOL-FAQ-V1-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Target branch/baseline: `codex/zai-glm52-dockerhost`
- Scope summary: Land PM's Agent Protocol FAQ V1 as built-in Ask this Agent platform mechanism knowledge and stop forwarding `chain_id` to centralized Marketplace AI endpoints by default.

## Change Steps

### Step 1: FAQ V1 Runtime Fixture

- Files/modules:
  - `app/runtime/platform_faq.py`
  - `tests/test_rag_agent_tool.py`
- Behavior change:
  - Add structured FAQ entries from the PM document.
  - Add deterministic keyword scoring and bounded chunk output.
  - Include explicit boundary entries for FAQ V1 gaps such as Profit Share, Management Fee formula, and paused-specific Redeem semantics.
- Verification:
  - `.venv/bin/python -m pytest tests/test_rag_agent_tool.py -q`

### Step 2: Retriever Adapter Integration

- Files/modules:
  - `app/runtime/adapters.py`
  - `app/runtime/agent_factory.py`
  - `app/runtime/chat_behavior.py`
  - `app/runtime/orchestrator.py`
  - `tests/test_rag_agent_tool.py`
  - `tests/test_agent_factory.py`
  - `tests/test_chat_behavior_policy.py`
- Behavior change:
  - `RetrieverAdapter.retrieve()` prepends FAQ V1 chunks to external RAG results when matched.
  - If no external knowledge base is configured, FAQ V1 still answers matching platform mechanism queries.
  - Non-matching queries keep the existing `no_knowledge_base` degraded response.
  - Empty model-emitted `search_knowledge` queries fall back to the current user prompt before retrieval.
  - Retrieval-start stream events use the same fallback query for live debugging.
  - Ask this Agent hides generic calculator, clock, and web-search tools so Marketplace data turns do not loop into unrelated tools.
  - Behavior policy answers `proxy_payload.chain_id` from the current system contract and forbids unofficial explanations on FAQ gaps.
- Verification:
  - `.venv/bin/python -m pytest tests/test_rag_agent_tool.py -q`
  - `.venv/bin/python -m pytest tests/test_agent_factory.py -q`
  - `.venv/bin/python -m pytest tests/test_chat_behavior_policy.py -q`
  - `.venv/bin/python -m pytest tests/test_orchestrator.py -q`
  - `.venv/bin/python -m pytest tests/test_tool_context_policy.py -q`

### Step 3: Marketplace Chain ID Default

- Files/modules:
  - `app/runtime/marketplace_ai.py`
  - `tests/test_marketplace_ai_client.py`
  - `tests/test_agent_marketplace_tools.py`
- Behavior change:
  - Resolve current Agent by address only.
  - Ignore `chain_id` in server context by default so centralized Marketplace AI requests omit the parameter.
- Verification:
  - `.venv/bin/python -m pytest tests/test_marketplace_ai_client.py tests/test_agent_marketplace_tools.py -q`

### Step 4: Eval Dataset And Deterministic Judge

- Files/modules:
  - `tests/chat_eval/golden_cases.jsonl`
  - `tests/chat_eval/judge.py`
- Behavior change:
  - Add FAQ V1 coverage cases for Mint/Redeem, Ask this Agent positioning, private-key custody, and risk disclaimer.
  - Update fee/paused expectations to acknowledge FAQ V1 gaps instead of rewarding invented formulas.
  - Update chain-id case to expect address-only Marketplace calls.
- Verification:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_eval.py -q`
  - `.venv/bin/python -m tests.chat_eval.scorecard --output /tmp/chat_eval_scorecard_faq_v1.json --strict`

### Step 5: Review And Release Gate

- Files/modules:
  - All files above.
- Verification:
  - `.venv/bin/python -m pytest tests/test_agent_factory.py tests/test_rag_agent_tool.py tests/test_marketplace_ai_client.py tests/test_agent_marketplace_tools.py tests/test_orchestrator.py tests/test_tool_context_policy.py tests/test_chat_behavior_policy.py tests/test_chat_behavior_eval.py -q`
  - `AI_BOUNDARY_APPROVED=1 PYTHON=.venv/bin/python scripts/verify_release.sh`
- Rollback:
  - Revert this plan/spec and runtime/test fixture changes. No DB rollback required.

## Risk Controls

- FAQ entries contain only PM-approved platform mechanism text, no secrets or user data.
- Built-in FAQ matching is bounded and only returns small chunks.
- Chain-id omission preserves the currently working centralized interface behavior.
