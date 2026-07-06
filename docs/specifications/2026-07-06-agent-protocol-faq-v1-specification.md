# 2026-07-06 Agent Protocol FAQ V1 Specification

## Context

- Spec ID: `SPEC-AGENT-PROTOCOL-FAQ-V1-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Source request: PM provided Lark document `Agent Protocol 协议市场 — FAQ 知识库V1.0` at `https://merlinchain.sg.larksuite.com/wiki/AeeywtmIniGvqxkTPF7l1ZWJgdf` and asked to land it into the system.
- Source document facts read from Chrome:
  - FAQ V1 is based on `Agent Protocol 官方市场PRD v1.8`, confirmed `2025-05-29`.
  - It is the fixed knowledge base for AI customer service / Ask this Agent.
  - Platform mechanism questions should be answered from this FAQ and should not be freely invented.
  - This FAQ only covers first-phase protocol marketplace content.
- Related existing specs:
  - `SPEC-MARKETPLACE-AI-INTERFACE-001`
  - `SPEC-ASK-THIS-AGENT-CHAT-EVAL-CLOSURE-001`
  - `SPEC-ASK-THIS-AGENT-TOOL-ROUTING-BUDGET-001`

## Product Semantics

- Ask this Agent must treat Agent Protocol FAQ V1 as authoritative fixed platform mechanism knowledge.
- When a user asks about FAQ-covered mechanisms, `search_knowledge` must be able to return FAQ chunks even when no external RAG knowledge base is configured.
- When a user asks about a platform mechanism not covered by FAQ V1, the assistant must say the current FAQ does not define that mechanism instead of filling the gap with generic financial or product assumptions.
- Examples covered by FAQ V1 include:
  - Mint / Redeem definition and two-step approval/execution flow.
  - Redeem disabled states for no shares and insufficient balance.
  - Supply Cap versus `totalSupply`.
  - Accept Token is contract-defined and not fixed to ETH.
  - Multi-chain deployment entries are independent and not cross-chain aggregated on Marketplace.
  - USD display and price-unavailable fallback.
  - Top Holders source and empty state.
  - DEX module conditional display.
  - Live Activity fields and separation from Agent Live Activities.
  - Marketplace list rules.
  - Create Agent steps.
  - Ask this Agent positioning as a centralized platform service, not part of the protocol.
  - Portfolio/Profile aggregation and visibility rules.
  - Browser/wallet support, degraded API behavior, navigation, private-key custody, chain-data integrity, and risk disclaimer.
- Examples not covered by FAQ V1:
  - Profit Share settlement timing or exact calculation.
  - Management Fee calculation formula.
  - Paused-state-specific Redeem restriction reason.

## API / Interface Contract

- No public `/chat` API request or response contract changes.
- `proxy_payload` remains the only public context field.
- Marketplace AI current-Agent resolution still accepts Agent address fields from server-owned context.
- Marketplace AI calls default to address-only routing:
  - `chain_id` in `proxy_payload`, `marketplace_agent`, or `agent` context must not be forwarded to the centralized `ai-context` or `ai-compute` endpoints by default.
  - If a future upstream contract requires `chain_id`, it must be introduced by a separate explicit policy/config/spec.

## Data / Schema / Projection Impact

- No database schema, migration, cache, or persistent projection changes.
- FAQ V1 entries and the related `chain_id` system-interface contract chunk are packaged as runtime code fixtures, not private credentials or user data.

## Architecture

- New runtime module:
  - `app/runtime/platform_faq.py`
- Updated runtime modules:
  - `app/runtime/adapters.py`
  - `app/runtime/agent_factory.py`
  - `app/runtime/chat_behavior.py`
  - `app/runtime/marketplace_ai.py`
  - `app/runtime/orchestrator.py`
- Updated tests/eval:
  - `tests/test_rag_agent_tool.py`
  - `tests/test_agent_factory.py`
  - `tests/test_chat_behavior_policy.py`
  - `tests/test_marketplace_ai_client.py`
  - `tests/test_agent_marketplace_tools.py`
  - `tests/chat_eval/golden_cases.jsonl`
  - `tests/chat_eval/judge.py`
- Runtime behavior:
  - `RetrieverAdapter.retrieve()` searches built-in FAQ V1 and related system-interface contract chunks first.
  - If no external `knowledge_base_id` exists, matching FAQ chunks are still returned with `source=agent_protocol_faq_v1`.
  - If an external RAG knowledge base exists, matching FAQ chunks are prepended to normal RAG chunks.
  - `search_knowledge` falls back to the current user prompt if the model emits an empty retrieval query.
  - Retrieval-start events use the same prompt fallback for observability when the model emits an empty query.
  - Ask this Agent exposes only `search_knowledge`, `marketplace_agent_context`, and `marketplace_agent_compute` tools; generic calculator, clock, and web-search tools remain hidden for this profile.
  - `search_knowledge` is budgeted to one call per turn and hidden after it is spent, preventing repeated retrieval loops from exhausting the model request limit.
  - The behavior policy tells the model that FAQ gaps must not be filled with unofficial generic explanations.
  - The output guardrail replaces FAQ-gap answers that append speculative "general understanding", "reasonable inference", possible-cause, or protocol-cause explanations with a bounded PM-doc-needed response.
  - The behavior policy states the current `proxy_payload.chain_id` rule: default not forwarded to Marketplace AI; address-only routing unless a future upstream contract reintroduces `chain_id`.
  - `extract_current_agent_ref()` returns the current Agent address and intentionally omits `chain_id` by default.

## Acceptance Criteria

- `search_knowledge("Mint 和 Redeem 分别是什么?")` returns FAQ V1 content without an external knowledge base.
- `search_knowledge("Profit Share 是什么时候收取?")` returns a FAQ V1 boundary chunk saying the mechanism is not covered, rather than returning no knowledge and inviting model invention.
- An empty model-emitted `search_knowledge` query uses the current user prompt for retrieval, so FAQ-covered questions still hit the built-in FAQ.
- Stream events for empty model-emitted retrieval queries show the effective user prompt rather than an empty query.
- Ask this Agent live runs cannot continue into calculator/clock/web-search loops after Marketplace tools have already answered a turn.
- Ask this Agent live runs cannot continue into repeated `search_knowledge` loops after the retrieval budget is spent.
- Questions about `proxy_payload.chain_id` receive the current address-only routing rule without requiring PM FAQ coverage.
- FAQ-gap answers do not append speculative risk-control, protocol-state, or timing explanations.
- Marketplace Agent context/compute tools do not pass `chain_id` even when `proxy_payload` includes it.
- Golden cases reflect the new PM FAQ source-of-truth and no longer expect invented Paused/fee formulas.
- Focused tests, deterministic chat eval scorecard, and release gate pass.

## Rollout / Rollback

- Rollout: deploy as a runtime-only behavior change; no migration or operator state change.
- Rollback: revert the FAQ fixture/search changes and chain-id extraction change. Public API callers remain compatible.

## External Follow-Ups

- PM should provide a later FAQ version for Profit Share timing, Management Fee calculation formula, and paused-state-specific Redeem semantics if those answers are required.
- Upstream Marketplace owner can ignore `chain_id` for current address-based calls unless a future ambiguity contract is specified.
