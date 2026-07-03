# 2026-07-03 Agent Identity Scope Guardrail Specification

Spec ID: `SPEC-AGENT-IDENTITY-SCOPE-GUARDRAIL-001`

Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`

## Context

- PRD/source request: the product positioning document defines this surface as `Ask this Agent`, a current trading Agent detail-page information assistant, not a generic AI/tool assistant.
- User-reported defect: asking the assistant to introduce itself returns generic capability claims such as calculator-like math, web search, time lookup, broad Q&A, and decision support.
- Target baseline: `codex/zai-glm52-dockerhost` at commit `d02007f339d05e113b843a7ee87f17d479fa4113`.
- Current behavior evidence:
  - Live DockerHost smoke on 2026-07-03, run `run_e1942e3c5f1948fcaeea4fa72ad9351f`, prompt `请介绍一下你自己。`
  - The answer said `我是一个 AI 智能助手`, listed `数学计算`, `联网搜索`, `时间查询`, `多方面的帮助`, and `决策建议`.
  - The run also invoked `marketplace_agent_context` without a current Agent address during self-introduction.
- Problem:
  - Generic tool/capability self-introduction conflicts with `SPEC-AGENT-POSITIONING-POLICY-001`.
  - The system prompt still exposes generic tool capabilities such as `calculator` and `clock`, which encourages model self-description as a utility bot.
  - Existing evals do not contain a self-introduction regression case.
  - A deterministic fixed self-introduction template is too rigid for the product experience; identity questions should still pass through the model while staying inside the PRD persona and scope.
- Non-goals:
  - No route, DB, streaming event, provider, Marketplace API, or deployment configuration change.
  - No removal of internal calculator/clock tools from the platform runtime in this slice.
  - No change to current Agent data field contracts.

## Product Semantics

- User/operator workflow:
  - When a user asks `你是谁`, `介绍一下你自己`, `你能做什么`, or equivalent identity/capability questions, the assistant should generate an answer as the Ask this Agent detail-page information assistant.
- State model:
  - Identity self-introduction is not a deterministic safe response; it goes through the model path.
  - Pure identity/capability questions are not data queries and should not call tools; tool use remains appropriate for specific current-Agent fields, metrics, reports, or Live Activities.
  - Other allowed Agent data questions continue through the model/tool path.
- Ownership and identity rules:
  - The assistant must not claim to be a generic AI assistant, calculator, web-search assistant, platform customer-support agent, market-news assistant, or cross-Agent comparison engine.
  - The assistant must not present internal tools as product capabilities.
- Presentation rules:
  - Identity answers should use readable Markdown structure: short opening sentence, concise sections, and bullet points.
  - Model-generated answers should prefer short headings, bullets, or compact tables for identity, capability, metric, and data-explanation answers; avoid one dense paragraph when multiple facts are present.
  - Formatting must improve scanability without turning the answer into marketing copy or adding unsupported claims.
- Permissions/authentication:
  - Unchanged.
- Empty, error, retry, timeout, duplicate, and partial-failure behavior:
  - Identity response succeeds as a normal assistant answer.
  - No dependency on current Agent address; if no Agent address is present, the identity answer still describes the role boundary, not unavailable tools.
- Compatibility and migration expectations:
  - Existing `/chat` request and response envelopes remain unchanged.

## API / Interface Contract

- Routes, commands, events, jobs, or UI surfaces:
  - Existing `/chat`, SSE, WebSocket, `/runs/{id}`, and conversation history only.
- Request fields and validation:
  - No new request field.
- Response/envelope fields and types:
  - No schema change.
- Status/error codes:
  - No new HTTP status.
- Backward compatibility:
  - Existing clients still receive a successful assistant answer.

## Data / Schema / Projection Impact

- Tables, indexes, migrations, backfills: none.
- Read models, projections, snapshots, caches: none.
- Historical data behavior: old generic answers remain historical records.
- Performance-sensitive paths: deterministic identity matching is local string/pattern matching before model/tool execution.

## Architecture

- Modules/files expected to change:
  - `app/runtime/chat_behavior.py`
  - `app/runtime/orchestrator.py`
  - `app/runtime/agent_factory.py`
  - `tests/test_chat_behavior_policy.py`
  - `tests/test_chat_behavior_eval.py`
  - `tests/test_orchestrator.py`
  - `tests/test_tool_context_policy.py`
  - `tests/chat_eval/golden_cases.jsonl`
  - `tests/chat_eval/evaluator.py`
- Data flow:
  1. Orchestrator evaluates the user message before model/tool execution.
  2. Identity/capability prompts pass as allowed input to the model.
  3. The system prompt and a server-owned turn instruction constrain model identity, scope, forbidden capability claims, and presentation.
  4. Non-identity allowed prompts continue through the existing model/tool flow.
  5. Security and language output guardrails remain deterministic for hidden-instruction, secret, and language violations; identity drift is handled through prompt/eval feedback rather than a fixed replacement template.
- Transaction/concurrency boundaries:
  - Same as existing deterministic guardrail path.
- Observability/logging/metrics:
  - Existing run plan `guardrail` metadata is reused.
- Rollback strategy:
  - Revert prompt narrowing, tests, and this spec/plan.

## Harness Classification

- Expected gate(s): `HARNESS-SPEC-FIRST-FEATURE`.
- Performance-sensitive class: low.
- Whether harness mapping must be extended: no.
- Required performance evidence: focused tests are sufficient.
- Focused verification commands:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_policy.py tests/test_chat_behavior_eval.py tests/test_orchestrator.py -q`
- Prerelease-grade verification commands:
  - `AI_BOUNDARY_APPROVED=1 make verify-release`

## Acceptance Criteria

- Functional:
  - `请介绍一下你自己。`, `你是谁?`, and `你能做什么?` pass through the model path instead of returning a deterministic fixed template.
  - Pure identity/capability prompts emit an LLM event but should not call Marketplace or utility tools.
  - Model-generated identity answers say it is the current Agent detail-page information assistant.
  - Model-generated identity answers do not claim to be a generic AI assistant, calculator, web-search assistant, platform support agent, market-news assistant, or investment adviser.
  - Model-generated identity answers name allowed user questions in PRD terms: current Agent metadata, contract parameters, on-chain/history metrics, Top Holders, Live Activities, and fixed platform mechanism knowledge.
  - Model-generated identity answers do not mention `数学计算`, `联网搜索`, `时间查询`, broad general Q&A, or decision-support capabilities as product capabilities.
  - Identity answers are not a single dense paragraph; they use Markdown section labels and bullet points for role, scope, and boundaries.
  - The default model prompt asks the LLM to use structured, readable Markdown formatting for multi-fact answers.
  - System prompt no longer advertises generic calculator/clock/web-search utility capabilities.
- Edge cases:
  - `这个 Agent 是做什么的?` remains an allowed current-Agent data question and does not get swallowed by the self-introduction guardrail.
  - Chinese and English identity prompts are both handled in the target language.
  - Hidden-instruction, secret, personal-wallet, real-money, and language guardrails remain deterministic.
- Compatibility:
  - Existing hidden-instruction, secret, wallet-data, language, and streaming output guardrails remain valid.
  - Existing tool-event tests for explicit tool-call harness behavior remain valid.
- Operational:
  - No secrets or real user wallet data are added to tests or docs.
- Evidence artifacts:
  - Focused tests, full tests, release gate output, and review notes.

## Review Notes

- Accepted assumptions:
  - Internal tools may still exist for engineering/runtime compatibility, but the product self-identity must not advertise them as user-facing capabilities.
  - Identity should be model-generated for product quality, while the PRD persona and scope remain server-owned prompt policy.
- Rejected alternatives:
  - Fixed deterministic identity templates were rejected because they feel rigid and low-quality for user-facing chat.
  - Removing calculator/clock tools entirely was deferred because this slice is about product identity behavior, not runtime tool inventory.
