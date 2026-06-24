# 2026-06-24 Chat Behavior Eval Framework Specification

## Context

- Spec ID: `SPEC-CHAT-BEHAVIOR-EVAL-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- PRD/source request: 继续细化 chat behavior framework, 将真实业务问题、理想回答、禁止回答、RAG 要求数据化, 让后续聊天效果调优可以通过 golden cases 回归验证。
- Target baseline: current `codex/zai-glm52-dockerhost` worktree with `SPEC-CHAT-BEHAVIOR-POLICY-001/v1` changes present.
- Current behavior:
  - `app/runtime/chat_behavior.py` contains deterministic v0 policy and guardrails.
  - `tests/test_chat_behavior_policy.py` and `tests/test_orchestrator.py` cover focused hard-coded examples.
  - Existing `tests/rag_eval/` is retrieval-only and does not express answer behavior, refusal boundaries, output safety, or product-style expectations.
- Problem:
  - Hard-coded unit tests do not scale well for iterative behavior tuning.
  - Future prompt/policy changes need a reusable case format that captures allowed/refused user intents, expected category, RAG requirements, desired answer traits, forbidden claims, and output safety checks.
  - A deterministic local gate is needed before adding slower Promptfoo or LLM-judge workflows.
- Non-goals:
  - No external LLM judge, Promptfoo execution, provider calls, Langfuse integration, DB schema change, route change, or runtime behavior change in this phase.
  - No claim that deterministic cases fully prove semantic safety.
  - No production persona finalization; product/legal copy remains future input.

## Product Semantics

- User/operator workflow:
  - Engineers add or update JSONL cases under `tests/chat_eval/` when they want to tune chat behavior.
  - Each case states what the user asks, whether the input guardrail should allow/refuse it, the expected category, optional RAG/tool expectations, answer traits, forbidden answer claims, and output sample checks.
  - Focused pytest validates the case schema, coverage mix, and current deterministic guardrail behavior.
- State model:
  - Eval cases are static test fixtures.
  - No runtime state, DB state, or API state changes.
- Ownership and identity rules:
  - Eval fixtures must not contain real secrets, user tokens, production logs, private account identifiers, or unredacted credentials.
  - Case ids are stable and unique so future failures are actionable.
- Permissions/authentication:
  - Not applicable; tests run locally.
- Empty, error, retry, timeout, duplicate, and partial-failure behavior:
  - Empty or duplicate case ids fail pytest.
  - Unsupported action/category values fail pytest.
  - Missing required acceptance fields fail pytest.
- Compatibility and migration expectations:
  - Existing focused tests remain valid.
  - `tests/chat_eval/` can later be reused by Promptfoo or another evaluator without changing the deterministic contract.

## API / Interface Contract

- Routes, commands, events, jobs, or UI surfaces:
  - No public API changes.
  - New local command: `.venv/bin/python -m pytest tests/test_chat_behavior_eval.py -q`
- Request fields and validation:
  - Not applicable.
- Response/envelope fields and types:
  - Not applicable.
- Status/error codes:
  - Not applicable.
- Pagination/sorting/filtering:
  - Not applicable.
- Backward compatibility:
  - Existing release/test commands remain unchanged.

## Data / Schema / Projection Impact

- Tables, indexes, migrations, backfills:
  - None.
- Read models, projections, snapshots, caches:
  - None.
- Rebuild or cleanup operators:
  - None.
- Historical data behavior:
  - Existing tests and eval fixtures are unaffected.
- Performance-sensitive queries or write paths:
  - Tests load a small JSONL fixture and call local deterministic policy functions only.

## Architecture

- Modules/files expected to change:
  - `tests/chat_eval/golden_cases.jsonl`
  - `tests/chat_eval/evaluator.py`
  - `tests/test_chat_behavior_eval.py`
  - `docs/specifications/2026-06-24-chat-behavior-eval-framework-specification.md`
  - `docs/implementation-plans/2026-06-24-chat-behavior-eval-framework-implementation-plan.md`
- Data flow:
  1. Pytest loads JSONL cases through `tests/chat_eval/evaluator.py`.
  2. Schema validator checks ids, fields, action/category enums, coverage tags, answer traits, forbidden claims, and secret hygiene.
  3. Input cases call `evaluate_user_message()`.
  4. Output sample cases call `evaluate_assistant_answer()`.
  5. Coverage gates assert that the fixture contains allow/refuse, false-positive, hidden-instruction, secret, real-money, RAG-required, and output-leak scenarios.
- Transaction/concurrency boundaries:
  - None.
- Observability/logging/metrics:
  - Pytest failure messages must include case id and reason.
- Rollback strategy:
  - Remove new eval fixture/test files and spec/plan; no runtime rollback required.

## Harness Classification

- Expected gate(s):
  - `HARNESS-SPEC-FIRST-FEATURE`
  - Focused pytest
  - `scripts/check_spec_contract.sh`
  - `scripts/check_harness_workflows.sh`
  - `make verify-release`
- Performance-sensitive class:
  - Not runtime performance-sensitive.
- Whether harness mapping must be extended:
  - No.
- Required performance evidence:
  - Focused test runtime remains local and deterministic.
- Focused verification commands:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_eval.py tests/test_chat_behavior_policy.py -q`
- Prerelease-grade verification commands:
  - `PYTHON=.venv/bin/python AI_BOUNDARY_APPROVED=1 make verify-release`

## Acceptance Criteria

- Functional:
  - `tests/chat_eval/golden_cases.jsonl` exists with stable case ids and at least 10 cases.
  - Cases cover allowed normal questions, false-positive traps, hidden instruction refusal, secret refusal, real-money direct-operation refusal, RAG-required allowed questions, and output-leak refusal.
  - Validator rejects duplicate ids, missing required fields, unsupported action/category values, and fixture text that contains real-looking secrets.
  - Focused pytest verifies current `chat_behavior` decisions against the golden cases.
  - Answer traits and forbidden claims are represented in data even if full answer-level generation is future work.
- Edge cases:
  - A benign API key setup question remains allowed.
  - A password-manager documentation question remains allowed.
  - A real-money risk-checklist question remains allowed.
  - Direct account/real-money operation remains refused.
- Compatibility:
  - No runtime/API/schema changes.
  - Existing behavior policy tests continue passing.
- Operational:
  - No external service, provider key, or network is required.
  - No real provider key, user token, or production log is committed.
- Evidence artifacts:
  - New spec/plan.
  - Golden cases fixture.
  - Focused pytest output.
  - Release harness output.

## Review Notes

- Open questions:
  - Exact MOSS production persona and legal/compliance phrasing still need product/legal input.
  - LLM judge thresholds and human-labeled answer scoring remain future phases.
- Accepted assumptions:
  - Deterministic schema/guardrail tests are the first eval layer.
  - JSONL is the right fixture shape because it can be reused by pytest and later Promptfoo-like tools.
- Rejected alternatives:
  - Add Promptfoo to release gate now: rejected because external npm/network/provider dependencies would make the gate less deterministic.
  - Store cases in Markdown only: rejected because pytest needs machine-readable contracts.
  - Test only hard-coded unit examples: rejected because it does not scale for iterative behavior tuning.
- Reviewer findings and resolution:
  - Pending implementation review.
