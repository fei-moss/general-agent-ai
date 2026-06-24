# 2026-06-24 Chat Behavior Policy and Guardrails Specification

## Context

- Spec ID: `SPEC-CHAT-BEHAVIOR-POLICY-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- PRD/source request: 将 2026-06-23 关于聊天效果调优、身份注入、拒答边界、guardrails、evals、tracing/prompt versioning 的引用调研结果, 按 Harness Driven Development 落地到 `general-agent-ai`。
- Target baseline: `codex/zai-glm52-dockerhost` at `17970a23c45ca7be594e3832450a48b2c2774457`。
- Current behavior:
  - `app/runtime/agent_factory.py` 用一个固定 `_SYSTEM_PROMPT` 定义通用中文助手、工具调用和不编造规则。
  - `AgentOrchestrator` 在 `run()` 内直接进入 Pydantic AI loop; 除 provider quota 和 usage limit 外, 没有业务身份、拒答边界、prompt version、输入 guardrail 或输出 guardrail。
  - RAG eval 已有 retrieval-only harness; 还没有 answer-level behavior eval。
- Problem:
  - 仅靠一个硬编码 system prompt 无法稳定表达产品身份、指令优先级、拒答边界、工具权限、RAG 引用和 prompt injection 防护。
  - 行为策略不可版本化, run plan 无法说明某次回答使用了哪版 policy。
  - 明显越权/泄密/真实资金操作请求仍会进入模型调用, 增加 provider 成本和安全风险。
- Research basis:
  - OpenAI Agents SDK documents input/output/tool guardrails: `https://openai.github.io/openai-agents-python/guardrails/`。
  - OpenAI Model Spec documents instruction hierarchy / chain of command: `https://model-spec.openai.com/`。
  - Pydantic AI supports instructions, tools, structured output, validators, usage limits, and streaming: `https://pydantic.dev/docs/ai/core-concepts/agent/`。
  - Promptfoo, OWASP LLM Top 10, NeMo Guardrails, and Langfuse document red-team eval, LLM application risks, programmable guardrails, and prompt/tracing lifecycle。
- Non-goals:
  - 不引入外部 LLM judge、Promptfoo npm gate、Langfuse server、NeMo Guardrails runtime dependency, or OpenAI Agents SDK migration in v0。
  - 不改变 `/chat` request/response fields, status codes, SSE/WS event names, or DB schema。
  - 不实现 fine-tuning, preference optimization, or provider-specific moderation API calls。
  - 不把 Pydantic AI 扩展成全局策略、队列、限流、持久化或分布式调度层。

## PRD Audit Summary

- covered:
  - The product intent is to move chat tuning from ad hoc prompt edits to policy + guardrail + eval/versioning.
  - The existing runtime has a clear insertion point: system prompt construction and `AgentOrchestrator.run()` before model calls.
  - Public API compatibility should be preserved.
- missing:
  - Final brand/persona copy for a production product assistant.
  - Full legal/compliance policy for regulated domains.
  - Human-labeled answer-level eval rubric.
- conflicts:
  - None blocking v0. The repo allows docs/tests freely and runtime edits with explicit task approval.
- assumptions:
  - v0 may use a conservative generic product-support assistant identity until product copy is finalized.
  - v0 refusal is returned as a successful assistant answer, not an error, because it is intentional policy behavior.
  - Deterministic local checks are preferable to external judge calls for release-gate stability.
- harness impact:
  - `HARNESS-SPEC-FIRST-FEATURE` because runtime behavior changes.
  - Focused tests must cover policy prompt construction, guardrail classification, and orchestrator short-circuit.
  - Release readiness remains `scripts/verify_release.sh` / `make verify-release`。
- go/no-go:
  - Go for v0 under the accepted assumptions above.

## Product Semantics

- User/operator workflow:
  - User still submits chat through existing `POST /chat` and consumes results through SSE/WS/run status/history.
  - For normal allowed requests, the run proceeds through the existing Pydantic AI agentic loop.
  - For deterministic input guardrail refusals, the run emits compatible lifecycle events, persists a safe assistant refusal, marks the run `SUCCEEDED`, and does not call the model or tools.
  - Operator can inspect run plan to see the policy version and guardrail decision.
- State model:
  - Allowed run: unchanged `PENDING -> RUNNING -> SUCCEEDED|FAILED|CANCELLED`。
  - Guardrail-refused run: `PENDING -> RUNNING -> SUCCEEDED` with assistant content explaining the safe refusal.
  - Guardrail refusal is not `FAILED`; it is a valid assistant response.
- Ownership and identity rules:
  - Existing conversation/run owner checks remain unchanged.
  - User input cannot override system/developer behavior policy, request hidden instructions, or request secrets.
  - Client metadata cannot select a different behavior policy in v0.
- Permissions/authentication:
  - Existing business endpoint auth remains unchanged.
  - Guardrail decisions do not create new public permission fields.
- Empty, error, retry, timeout, duplicate, and partial-failure behavior:
  - Empty message handling remains owned by API validation.
  - Duplicate/idempotent request behavior remains unchanged.
  - Guardrail short-circuit avoids provider quota acquisition, LLM generation, retrieval, and tool execution.
  - If run_repo update fails during guardrail handling, the orchestrator still persists best-effort assistant content and emits terminal events, matching existing resilience style.
  - Output guardrail replacement uses a safe fallback answer if model output appears to expose hidden instructions or secrets.
- Compatibility and migration expectations:
  - No route, schema, migration, event type, or client contract changes.
  - Existing mock provider behavior remains deterministic for allowed requests.
  - Run plan gains additive keys only: `policy_version` and optional `guardrail` object.
  - Client metadata keys that look like policy controls, such as `policy_version`, `guardrail`, `disable_guardrails`, `disable_guardrail`, and `behavior_policy`, are removed from recorded plan metadata so they cannot shadow server-owned policy fields.

## API / Interface Contract

- Routes, commands, events, jobs, or UI surfaces:
  - Existing `/chat`, `/stream/{agent_run_id}`, `WS /ws/{agent_run_id}`, `/runs/{agent_run_id}`, and conversation history remain unchanged.
- Request fields and validation:
  - No new request fields.
  - User-provided `metadata` cannot override policy version or disable guardrails.
- Response/envelope fields and types:
  - `ChatAccepted` remains unchanged.
  - `RUN_COMPLETED.data.content` includes the refusal text for guardrail-refused runs.
- Status/error codes:
  - No new HTTP status codes.
  - Guardrail refusal is not surfaced as `ERROR` unless an unexpected internal exception occurs.
- Pagination/sorting/filtering:
  - Not applicable.
- Backward compatibility:
  - Existing clients consuming terminal `RUN_COMPLETED` keep working.
  - Event names remain from the existing `EventType` enum.

## Data / Schema / Projection Impact

- Tables, indexes, migrations, backfills:
  - None.
- Read models, projections, snapshots, caches:
  - `agent_run.plan` receives additive policy/guardrail metadata through existing plan storage.
  - Run-plan `metadata` excludes client-provided behavior-policy override keys; top-level policy fields are server-owned.
- Rebuild or cleanup operators:
  - None.
- Historical data behavior:
  - Historical runs have no `policy_version`; readers must tolerate missing fields.
- Performance-sensitive queries or write paths:
  - Guardrail checks are local string/pattern checks and must run before provider quota acquisition.
  - No DB query is added before guardrail evaluation beyond existing orchestration state writes.
  - v0 buffers assistant answer token chunks before client emission so output guardrail can prevent high-confidence leaks from reaching `TOKEN` events. This preserves event compatibility but trades off realtime token flush for safer first-phase behavior.

## Architecture

- Modules/files expected to change:
  - `app/runtime/chat_behavior.py` new policy and deterministic guardrail module.
  - `app/runtime/agent_factory.py` to build the Agent system prompt from the policy module.
  - `app/runtime/orchestrator.py` to short-circuit deterministic refusals, apply output guardrail, and include policy version in plan.
  - `tests/test_chat_behavior_policy.py`, `tests/test_agent_factory.py`, and `tests/test_orchestrator.py` for focused coverage.
  - `docs/specifications/2026-06-24-chat-behavior-policy-and-guardrails-specification.md` and matching implementation plan.
- Data flow:
  1. API accepts and persists the user message exactly as before.
  2. Orchestrator emits `RUN_STARTED`.
  3. Orchestrator evaluates input guardrail locally.
  4. If refused, orchestrator writes plan with policy version and guardrail metadata, persists safe answer, emits `RESULT_COMPOSED` and `RUN_COMPLETED`.
  5. If allowed, orchestrator proceeds through existing history load, provider quota, and Pydantic AI loop. Assistant token chunks are buffered until the final answer passes output guardrail, then only safe token chunks are emitted before persistence and terminal event.
- Transaction/concurrency boundaries:
  - No new lock or transaction boundary.
  - Guardrail short-circuit must not hold DB sessions while waiting on external services because it performs no external calls.
- Observability/logging/metrics:
  - Run plan records policy version and guardrail category/action/reason code.
  - Logs must not include secrets, raw provider tokens, or hidden instructions.
- Rollback strategy:
  - Revert runtime module changes and tests; no DB rollback required.
  - Missing `policy_version` remains tolerated.

## Harness Classification

- Expected gate(s):
  - `HARNESS-SPEC-FIRST-FEATURE`
  - `scripts/check_ai_boundaries.sh`
  - `scripts/check_spec_contract.sh`
  - `scripts/check_harness_workflows.sh`
  - Focused pytest and `scripts/verify_release.sh`
- Performance-sensitive class:
  - Low overhead runtime hot path; local checks only.
- Whether harness mapping must be extended:
  - No.
- Required performance evidence:
  - Focused tests confirm guardrail refusal bypasses model/tool execution.
  - Focused tests confirm guardrail refusal also bypasses provider limiter acquisition under real-provider settings.
- Focused verification commands:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_policy.py tests/test_agent_factory.py tests/test_orchestrator.py -q`
  - `scripts/check_ai_boundaries.sh`
  - `scripts/check_spec_contract.sh`
  - `scripts/check_harness_workflows.sh`
- Prerelease-grade verification commands:
  - `scripts/verify_release.sh`
  - `make verify-release`

## Acceptance Criteria

- Functional:
  - A versioned default chat behavior policy exists and builds the Agent system prompt.
  - Prompt contains identity, instruction hierarchy, tool policy, RAG/uncertainty policy, and refusal boundaries.
  - Input guardrail refuses at least hidden-instruction exfiltration, credential/secret requests, and direct real-money/external-account operation requests.
  - Guardrail-refused runs emit compatible terminal events, persist assistant content, and skip model/tool execution.
  - Allowed requests keep existing mock agent retrieval and tool behavior.
  - Output guardrail replaces responses that appear to reveal hidden instructions or secrets.
- Edge cases:
  - Whitespace and empty messages remain API-level validation, not behavior policy.
  - Prompt injection phrasing is handled without exposing hidden instructions.
  - Benign mentions of "password manager" or "API key setup docs" are not automatically refused unless they request secret values or credential extraction.
  - Conceptual behavior-tuning questions and real-money risk-checklist questions are allowed unless they request hidden instructions, secrets, or direct account operations.
- Compatibility:
  - No public API contract, schema, event type, or provider configuration break.
  - Historical runs without policy metadata remain valid.
- Operational:
  - No real provider key, user token, or hidden prompt is written to docs/tests/logs.
  - No external service is required for focused tests.
- Evidence artifacts:
  - Specification and implementation plan.
  - Focused pytest output.
  - Release harness output or explicit blocker.

## Review Notes

- Open questions:
  - Final production brand/persona copy and regulated-domain policy require product/legal input before public launch.
  - Answer-level LLM judge eval remains a future phase once labeled examples exist.
- Accepted assumptions:
  - v0 uses deterministic local policy checks.
  - Refusal is a successful assistant answer.
  - Policy version is additive run-plan metadata, not a DB schema change.
- Rejected alternatives:
  - Replace Pydantic AI with OpenAI Agents SDK now: rejected because the repo is multi-provider and already has Pydantic AI runtime boundaries.
  - Fine-tune first: rejected because behavior contracts and evals do not exist yet.
  - Add external moderation/judge dependency in release gate: rejected for deterministic local verification in v0.
- Reviewer findings and resolution:
  - Code review found that applying output guardrail only after streaming could leak unsafe `TOKEN` events. Resolution: buffer assistant token chunks until output guardrail passes, and emit only safe answer chunks.
