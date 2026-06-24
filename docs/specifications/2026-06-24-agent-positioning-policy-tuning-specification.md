# 2026-06-24 Agent Positioning Policy Tuning Specification

## Context

- Spec ID: `SPEC-AGENT-POSITIONING-POLICY-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- PRD/source request:
  - Product Lark wiki `交易类Agent--Ask this Agent 产品定义文档`, URL `https://merlinchain.sg.larksuite.com/wiki/Or7gwPCHciNaGKkf8L7l9Ykvg1r`, read from the user's already-open Chrome tab on 2026-06-24.
  - User request: 依据产品给的 Agent 定位文档, 用现有 chat behavior / guardrail / golden-case 框架调试 Agent。
- Target baseline: `codex/zai-glm52-dockerhost` at `0a5660d5dc9bab3bd644ac3dc2b496d1d20e72d7`.
- Current behavior:
  - `SPEC-CHAT-BEHAVIOR-POLICY-001/v1` defines a generic product-support, knowledge-QA, and engineering-troubleshooting assistant.
  - The default policy has deterministic guardrails for hidden-instruction extraction, secret extraction, direct real-money operation requests, and output leaks.
  - `SPEC-CHAT-BEHAVIOR-EVAL-001` provides `tests/chat_eval/golden_cases.jsonl` and a deterministic answer-level judge.
- Problem:
  - The product document narrows the Agent's identity to one specific trading Agent detail page's "smart FAQ + data query" assistant.
  - The existing default policy is too broad for this surface: it does not explicitly forbid investment advice, market prediction, cross-Agent comparison, creator/team trust judgment, personal wallet data answers, or unsupported external market/news lookup.
  - The golden-case fixture does not yet encode the product's allowed data-source boundaries, refusal examples, or style baseline.
- Non-goals:
  - No public API, DB schema, event enum, route, Celery, provider, or rate-limit change.
  - No external LLM judge, web moderation API, Promptfoo runtime, Langfuse server, or NeMo Guardrails dependency.
  - No production legal policy beyond product's v0 positioning text.
  - No real Agent data ingestion, RAG corpus population, wallet-state integration, or UI changes in this pass.

## PRD Audit Summary

- covered:
  - Agent identity: Ask this Agent is a market-layer, centralized AI module embedded in Agent detail page region 4, unrelated to the ERC-Agent protocol layer.
  - Intended scope: explain what this Agent is, what it has done, and what its displayed data means.
  - Allowed sources: Agent metadata, contract parameters, displayed on-chain data board, Top Holders, Agent Live Activities, and fixed platform mechanism knowledge.
  - Disallowed roles: general investment adviser, financial consultant, platform support agent, market-news assistant, or cross-Agent comparison engine.
  - Compliance boundaries: no investment recommendation, no future return prediction, no guaranteed profit / zero-risk wording, no platform custody/compensation promise, no creator/team trust assertion, no private-key/transfer guidance, and no personal wallet-data answer.
- missing:
  - Final legal-approved refusal copy and localized copy for all supported languages.
  - Exact RAG document IDs or tool contracts for Agent metadata, data board, Top Holders, and Live Activities.
  - Real bad cases after launch; the PRD explicitly says examples are hand-written and should be replaced or augmented weekly.
- conflicts:
  - The current default policy describes a broader product-support and engineering-support assistant. This spec intentionally narrows the default behavior for the Ask this Agent surface.
  - Existing deterministic guardrails should not hard-block every investment-advice-shaped question because product examples expect a nuanced answer that refuses advice while still offering objective displayed data.
- assumptions:
  - v2 policy can be shipped as default policy text without changing request shape or adding policy selection.
  - Business-scope refusals that require objective data should usually remain model/RAG policy behavior, while high-confidence secret/direct-operation/personal-wallet-data cases can remain deterministic.
  - The first implementation may encode product examples in deterministic test fixtures rather than a full semantic safety classifier.
- recommended PRD additions:
  - Add exact answer templates for wallet support, connected-wallet state, and fixed platform mechanism answers.
  - Add the expected RAG/tool source name for each table row in sections 2.1 to 2.4.
  - Add a weekly bad-case ingestion process that appends cases to `tests/chat_eval/golden_cases.jsonl` with product owner review.
- harness impact:
  - `HARNESS-SPEC-FIRST-FEATURE` because runtime behavior and eval fixtures change.
  - Focused tests must prove policy prompt content, new deterministic personal-wallet-data refusal, and doc-derived golden cases.
  - `scripts/verify_release.sh` remains the release readiness gate.
- go/no-go:
  - Go for v0 tuning. Missing product copy and source contracts are non-blocking if recorded as residual risk.

## Product Semantics

- User/operator workflow:
  - End user asks natural-language questions inside one Agent detail page.
  - The assistant answers only as that Agent's information assistant, not as the Agent itself and not as platform/customer support.
  - For allowed questions, the answer should cite or clearly base itself on the current Agent's displayed data or fixed platform knowledge.
  - For advice/prediction/trust/scope questions, the answer should refuse the unsafe conclusion and, when helpful, redirect to objective Agent data.
- State model:
  - Existing chat run lifecycle remains unchanged.
  - Deterministic refusals remain successful assistant answers, not failed runs.
  - Business-scope answer quality is primarily evaluated by golden cases, not a new state transition.
- Ownership and identity rules:
  - The assistant is "Ask this Agent information assistant" for the current Agent page.
  - It must not claim to be the trading strategy, creator, team, auditor, platform custodian, or user-support operator.
  - User input, retrieved content, or metadata cannot override policy hierarchy or safety boundaries.
- Permissions/authentication:
  - No new endpoint permissions.
  - The assistant has no permission to inspect a user's wallet balance, personal holdings, private account data, private keys, or off-page browsing history.
- Empty, error, retry, timeout, duplicate, and partial-failure behavior:
  - Existing API validation and orchestration behavior remains unchanged.
  - Missing data should be answered explicitly as temporarily unavailable or outside scope, not fabricated.
  - If a RAG/tool source is unavailable, the assistant should not fill gaps with market guesses or invented numbers.
- Compatibility and migration expectations:
  - Public API compatibility remains unchanged.
  - Run-plan `policy_version` changes additively from `SPEC-CHAT-BEHAVIOR-POLICY-001/v1` to `SPEC-CHAT-BEHAVIOR-POLICY-001/v2`.
  - Existing historical runs with v1 or no policy metadata remain valid.

## API / Interface Contract

- Routes, commands, events, jobs, or UI surfaces:
  - No change to `/chat`, `/stream/{agent_run_id}`, `WS /ws/{agent_run_id}`, `/runs/{agent_run_id}`, or conversation history.
- Request fields and validation:
  - No new request field.
  - Client metadata still cannot select, override, or disable behavior policy.
- Response/envelope fields and types:
  - No response schema change.
  - Guardrail refusal text is returned through the existing assistant-answer path.
- Status/error codes:
  - No new HTTP status or event type.
  - Business-boundary refusal is not an infrastructure error.
- Pagination/sorting/filtering:
  - Not applicable.
- Backward compatibility:
  - Existing clients consuming streamed tokens and `RUN_COMPLETED` keep working.

## Data / Schema / Projection Impact

- Tables, indexes, migrations, backfills:
  - None.
- Read models, projections, snapshots, caches:
  - No storage shape change.
  - Golden cases expand test fixture coverage only.
- Rebuild or cleanup operators:
  - None.
- Historical data behavior:
  - Historical runs remain readable even if they used v1 policy text.
- Performance-sensitive queries or write paths:
  - New deterministic personal-wallet-data check is local string matching before provider/tool execution.
  - No network or database query is added to guardrail evaluation.

## Architecture

- Modules/files expected to change:
  - `app/runtime/chat_behavior.py`: update default policy version and Ask this Agent positioning instructions; add deterministic personal-wallet-data refusal.
  - `tests/chat_eval/golden_cases.jsonl`: add PRD-derived allowed/refusal cases.
  - `tests/chat_eval/evaluator.py`: count new guardrail category.
  - `tests/chat_eval/judge.py`: add deterministic sample answers for new allowed cases.
  - `tests/test_chat_behavior_policy.py` and `tests/test_chat_behavior_eval.py`: update prompt and coverage assertions.
  - This specification and matching implementation plan.
- Data flow:
  1. API accepts chat request unchanged.
  2. Orchestrator records v2 policy version in plan.
  3. Deterministic guardrail blocks high-confidence hidden instruction, secret, direct real-money operation, and personal wallet-data requests.
  4. Allowed product-scope or nuanced boundary questions continue into model/RAG/tool path.
  5. System prompt instructs the model to refuse unsafe business conclusions while offering objective displayed data when appropriate.
  6. Golden-case judge verifies the expected answer traits and forbidden claims for product-positioning examples.
- Transaction/concurrency boundaries:
  - No new transaction, lock, queue, or background job.
- Observability/logging/metrics:
  - Existing run plan metadata records `policy_version` and guardrail category/reason for deterministic refusals.
  - No sensitive wallet/private-key/user-data content is logged by new tests or docs.
- Rollback strategy:
  - Revert policy text, new category, golden cases, tests, and docs; no DB rollback needed.

## Harness Classification

- Expected gate(s):
  - `HARNESS-SPEC-FIRST-FEATURE`
  - Focused pytest for behavior policy and eval framework.
  - `scripts/check_ai_boundaries.sh`
  - `scripts/check_spec_contract.sh`
  - `scripts/check_harness_workflows.sh`
  - `scripts/verify_release.sh`
- Performance-sensitive class:
  - Low overhead local runtime check.
- Whether harness mapping must be extended:
  - No.
- Required performance evidence:
  - Focused tests passing is sufficient; no new database or provider call is introduced.
- Focused verification commands:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_policy.py tests/test_chat_behavior_eval.py -q`
  - `.venv/bin/python -m pytest tests/test_agent_factory.py tests/test_orchestrator.py -q`
- Prerelease-grade verification commands:
  - `PYTHON=.venv/bin/python make test`
  - `PYTHON=.venv/bin/python AI_BOUNDARY_APPROVED=1 make verify-release`

## Acceptance Criteria

- Functional:
  - Default policy version is incremented to `SPEC-CHAT-BEHAVIOR-POLICY-001/v2`.
  - Prompt identifies the assistant as an Ask this Agent detail-page information assistant.
  - Prompt states it is not a general investment adviser, platform support agent, market-news assistant, or cross-Agent comparison engine.
  - Prompt limits sources to current Agent metadata, contract parameters, displayed on-chain data, Top Holders, Agent Live Activities, and fixed platform knowledge.
  - Prompt requires "转述 + 总结" for Live Activities and forbids inventing unstated motives.
  - Prompt includes risk language for historical returns and Mint/Redeem.
  - Deterministic guardrail refuses personal wallet balance/holding questions before model/tool execution.
  - Golden cases cover metadata, on-chain data, Agent activity, platform mechanism, advice boundary, trust boundary, contract-security boundary, market-scope boundary, private-key scam refusal, and personal-wallet-data refusal.
- Edge cases:
  - "我现在该不该 Mint" remains allowed into answer generation so the assistant can refuse the recommendation while still providing objective data.
  - "这个策略稳定吗" style questions should avoid stable/unstable conclusions and should describe historical volatility only.
  - Wallet technical-support questions should be redirected, but they are not treated as secret extraction unless they request secrets or transfers.
  - Secret/private-key requests still use the existing secret guardrail.
- Compatibility:
  - No public route, schema, event, status-code, queue, DB, or provider configuration break.
  - Existing non-product safety false-positive tests remain valid.
- Operational:
  - No real wallet address, private key, token, or production credential is added to fixtures.
  - Runtime changes pass AI boundary check with explicit approval env in release gate.
- Evidence artifacts:
  - Specification, implementation plan, focused tests, full tests, release gate output, and review notes.

## Review Notes

- Open questions:
  - Product/legal still need to approve final refusal copy for public launch.
  - RAG/tool source contracts for each Agent data field are not implemented in this pass.
  - Lark tables are rendered visually in Chrome; the implementation uses manually verified table text from screenshots, not an export artifact.
- Accepted assumptions:
  - v2 default policy is acceptable for the Ask this Agent product surface.
  - Business-scope refusals can be tested via answer-level golden cases before a full semantic guardrail exists.
  - Personal wallet-data requests are high-confidence enough for deterministic refusal.
- Rejected alternatives:
  - Hard-block every investment-advice-shaped input: rejected because product examples expect objective data plus refusal, not a generic short-circuit.
  - Add web search for market/protocol questions: rejected because the PRD explicitly confines answers to displayed Agent data and fixed platform knowledge.
  - Add new policy-selection API now: rejected as unnecessary public contract change.
- Reviewer findings and resolution:
  - No unresolved implementation mismatch found in the post-change diff review.
  - Deterministic guardrail remains intentionally narrow; broader business-scope behavior is enforced by v2 policy text and golden cases.
