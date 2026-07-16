# Platform Mechanism Absorption Follow-Up Specification

Spec ID: `SPEC-PLATFORM-MECHANISM-ABSORPTION-002`
Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
Date: 2026-07-03

## Context

`SPEC-PLATFORM-MECHANISM-ABSORPTION-001` absorbed the first batch of reusable mechanisms from `world-cup-chat-server`: provider key pools, route-aware API limiting, and generic `run_context` propagation. The remaining reusable mechanisms require separate contracts because they touch conversation identity, tool exposure, behavior profiles, and release gates.

## Goals

- Add a generic conversation anchor contract so callers can bind a server-side domain object to one durable conversation without importing World Cup-specific `match_id` semantics.
- Add a context-bound masking and tool-permission layer so server-injected runtime context can be exposed to the model only after sensitive/locked values are masked, and tools can be disabled by policy.
- Add a behavior profile registry so future domain-specific policies can be selected by server-owned configuration without ad hoc prompt rewrites.
- Add a root production deployment contract checker that verifies DockerHost/runtime/secret-hygiene release prerequisites as executable evidence.

## Non-Goals

- Do not add World Cup business fields, paid block names, prediction constants, or Polymarket-specific semantics.
- Do not let client metadata override behavior policy, disable guardrails, or grant tools.
- Do not expose raw secrets, provider keys, tokens, locked paid values, or raw private context in run plans, prompts, logs, tool calls, readiness responses, or release artifacts.
- Do not perform a live DockerHost deployment in this implementation slice.

## Requirements

### `SPEC-PLATFORM-MECHANISM-ABSORPTION-002-R1` Conversation Anchors

- `ChatRequest` MUST accept an optional `conversation_anchor` object with `type` and `key`.
- Anchor type/key MUST be normalized and bounded to safe identifier lengths.
- If `conversation_id` is absent and a matching anchor exists for the authenticated user, `/chat` MUST reuse the anchored conversation.
- If a new conversation is created with an anchor, the API MUST bind `(user_id, anchor_type, anchor_key)` to the conversation.
- Anchor persistence MUST be additive and MUST NOT change the existing `conversation` table columns in this slice.
- Duplicate anchors MUST be prevented by a unique user/type/key constraint.

### `SPEC-PLATFORM-MECHANISM-ABSORPTION-002-R2` Context Masking And Tool Permissions

- Runtime context exposed to the Agent prompt MUST be masked by a deterministic server-side function.
- Objects marked as locked, secret, private, hidden, or inaccessible MUST not expose their raw `value`/`content`/`text` payloads to the model.
- The masked context instruction MUST be additive and omitted when no safe context exists.
- Tool functions MUST honor `run_context.tool_permissions.denied` and return a structured denial instead of executing blocked tools.
- Tool permission denials MUST not bypass input/output guardrails.

### `SPEC-PLATFORM-MECHANISM-ABSORPTION-002-R3` Behavior Profiles

- Behavior policy selection MUST be registry-based and server-owned.
- The default profile MUST preserve the current Ask this Agent behavior.
- Unknown profile names MUST fail closed to the default profile.
- Run plans MUST include `behavior_profile` alongside `policy_version`.
- Client `metadata` MUST NOT choose a behavior profile.

### `SPEC-PLATFORM-MECHANISM-ABSORPTION-002-R4` Production Deployment Contract

- Add a root `production-deployment-contract.md` that states DockerHost Git-pull deployment, secret-injection, readiness, smoke, rollback, and cleanup requirements.
- Add an executable checker that validates the root contract and existing DockerHost runbook include required release evidence and secret-hygiene language.
- `scripts/verify_release.sh` MUST run the production deployment contract checker.

## Verification

- Focused tests:
  - `tests/test_conversation_anchors.py`
  - `tests/test_tool_context_policy.py`
  - `tests/test_chat_behavior_profiles.py`
  - `tests/test_production_deployment_contract.py`
- Regression tests:
  - `tests/test_chat_routing.py`
  - `tests/test_agent_factory.py`
  - `tests/test_orchestrator.py`
  - `tests/test_production_readiness.py`
- Harness/release checks:
  - `scripts/check_ai_boundaries.sh`
  - `scripts/check_spec_contract.sh`
  - `scripts/check_spec_registry.sh`
  - `scripts/verify_release.sh`

## Compatibility

- Existing clients that omit `conversation_anchor` and `run_context` continue unchanged.
- Existing conversations without anchors remain valid.
- Behavior profile defaults preserve current prompt and guardrail semantics.
- The deployment checker is additive; it does not run network or DockerHost commands.
