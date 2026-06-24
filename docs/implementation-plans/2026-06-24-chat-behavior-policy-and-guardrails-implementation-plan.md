# 2026-06-24 Chat Behavior Policy and Guardrails Implementation Plan

## Plan Header

- Specification: `docs/specifications/2026-06-24-chat-behavior-policy-and-guardrails-specification.md`
- Spec ID: `SPEC-CHAT-BEHAVIOR-POLICY-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Target branch/baseline: `codex/zai-glm52-dockerhost` at `17970a23c45ca7be594e3832450a48b2c2774457`
- Scope summary: Add a versioned chat behavior policy, deterministic input/output guardrails, run-plan policy metadata, and focused tests while preserving `/chat`, SSE/WS, DB schema, and provider configuration compatibility.
- Out of scope:
  - External judge/eval services, Promptfoo execution, Langfuse integration, NeMo Guardrails dependency, OpenAI Agents SDK migration, fine-tuning, DB migrations, API shape changes.

## Change Steps

### Step 1: Add Focused Tests First

- Files/modules:
  - `tests/test_chat_behavior_policy.py`
  - `tests/test_agent_factory.py`
  - `tests/test_orchestrator.py`
- Behavior change:
  - Express policy prompt contract, guardrail allow/refuse cases, plan metadata, and orchestrator short-circuit before implementation.
- Data contract impact:
  - None.
- Tests to add/update:
  - Policy prompt includes versioned identity, instruction hierarchy, refusal boundaries, RAG/tool policy.
  - Input guardrail refuses hidden instruction extraction, secret/credential extraction, and direct real-money/account operation requests.
  - Input guardrail allows benign credential documentation questions.
  - Agent factory uses the policy prompt.
  - Orchestrator refusal persists safe answer, emits `RUN_COMPLETED` success, and skips retriever/tool/model phases.
  - Orchestrator refusal skips provider limiter acquisition under real-provider settings.
  - Plan snapshot includes `policy_version`.
  - Client metadata cannot shadow server-owned policy/guardrail plan fields.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_policy.py tests/test_agent_factory.py tests/test_orchestrator.py -q`
- Rollback or compatibility note:
  - Tests only; expected to fail until runtime implementation lands.

### Step 2: Add Behavior Policy Module

- Files/modules:
  - `app/runtime/chat_behavior.py`
- Behavior change:
  - Introduce `ChatBehaviorPolicy`, `GuardrailDecision`, action/category constants, `DEFAULT_CHAT_BEHAVIOR_POLICY`, `build_system_prompt()`, `evaluate_user_message()`, and `evaluate_assistant_answer()`.
- Data contract impact:
  - None.
- Tests to add/update:
  - `tests/test_chat_behavior_policy.py`
- Verification command:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_policy.py -q`
- Rollback or compatibility note:
  - Module is dependency-free and can be removed without migration.

### Step 3: Wire Policy Prompt Into Agent Factory

- Files/modules:
  - `app/runtime/agent_factory.py`
- Behavior change:
  - Replace hardcoded `_SYSTEM_PROMPT` with `build_system_prompt(DEFAULT_CHAT_BEHAVIOR_POLICY)`.
  - Preserve tool registration and model selection behavior.
- Data contract impact:
  - None.
- Tests to add/update:
  - `tests/test_agent_factory.py`
- Verification command:
  - `.venv/bin/python -m pytest tests/test_agent_factory.py -q`
- Rollback or compatibility note:
  - Existing mock agent flow remains expected to pass.

### Step 4: Wire Guardrails Into Orchestrator

- Files/modules:
  - `app/runtime/orchestrator.py`
- Behavior change:
  - Include `policy_version` in `_plan_snapshot()`.
  - Strip client metadata keys that try to override policy/guardrail behavior from plan metadata.
  - Evaluate input guardrail immediately after `RUN_STARTED`, before history/model/provider/tool execution.
  - For refused input, mark running with plan, emit `RESULT_COMPOSED`, persist safe assistant response, mark succeeded, emit terminal success.
  - For allowed model output, buffer assistant token chunks, run output guardrail, emit only safe token chunks, then persist and emit terminal event.
- Data contract impact:
  - Additive `agent_run.plan` keys only.
- Tests to add/update:
  - `tests/test_orchestrator.py`
- Verification command:
  - `.venv/bin/python -m pytest tests/test_orchestrator.py -q`
- Rollback or compatibility note:
  - Public events and response envelope remain compatible.

### Step 5: Harness Checks and Review

- Files/modules:
  - All changed docs/tests/runtime files.
- Behavior change:
  - None beyond implementation.
- Data contract impact:
  - None.
- Tests to add/update:
  - Fix only failures tied to this spec.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_policy.py tests/test_agent_factory.py tests/test_orchestrator.py -q`
  - `scripts/check_ai_boundaries.sh`
  - `scripts/check_spec_contract.sh`
  - `scripts/check_harness_workflows.sh`
  - `scripts/verify_release.sh`
- Rollback or compatibility note:
  - If full release gate fails for environmental reasons, record blocker and focused-test evidence.

## Risk Controls

- Public contract risks:
  - No public API shape or event enum changes.
  - Refusal returns existing terminal `RUN_COMPLETED` success with assistant content.
- Money/accounting/security risks:
  - Direct real-money/account operation requests are refused before model/tool execution.
  - Tests must prove provider/model/tool path is bypassed on deterministic refusal.
- Migration/rebuild risks:
  - No migration or rebuild.
- Performance risks:
  - Guardrails are deterministic local string checks.
  - No external calls added to hot path.
  - Output guardrail buffers final answer chunks before emitting `TOKEN`; this is an explicit v0 safety tradeoff and should be revisited when a streaming-safe output classifier exists.
- Deployment/test-branch risks:
  - Existing release gate remains authoritative.
- Unrelated local changes to avoid:
  - Do not stage `.artifacts/`, `__pycache__`, local runbooks, secrets, or unrelated DockerHost/Z.AI work.

## Completion Criteria

- Specification still matches implementation.
- Focused tests pass.
- AI boundary, spec contract, and harness workflow checks pass.
- Release verification passes or a concrete blocker is reported.
- Code review loop finds no unresolved contract/test/security issue.
