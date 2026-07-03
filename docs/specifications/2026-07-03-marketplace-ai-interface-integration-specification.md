# Marketplace AI Interface Integration Specification

Spec ID: `SPEC-MARKETPLACE-AI-INTERFACE-001`
Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
Date: 2026-07-03

## Context

Marketplace backend now exposes centralized read-only Agent data for ai-chat:

- `GET /api/v1/agents/{address}/ai-context`
- `POST /api/v1/agents/{address}/ai-compute`

The contract is described by `/Users/chris/Downloads/ai-chat-interface.md` and the required question coverage is described by `/Users/chris/Downloads/ai-chat-interface-request.md`. Live dev smoke against `https://app-df-moss-site-agent-marketplace-dev.dkhost.vixmk-yo.org` confirmed the response shapes on 2026-07-03.

The existing platform truth is:

- `SPEC-PLATFORM-MECHANISM-ABSORPTION-001` added generic `run_context` propagation.
- `SPEC-PLATFORM-MECHANISM-ABSORPTION-002` added masked prompt exposure and context-bound tool permissions.
- `SPEC-CHAT-BEHAVIOR-POLICY-001/v3` scopes Ask this Agent answers to the current Agent detail page and forbids invented metrics.

## Goals

- Add a read-only Marketplace AI client for `ai-context` and `ai-compute`.
- Expose the client through Agent tools that are scoped to the current server-injected Agent context.
- Preserve Marketplace status semantics: `unsupported`, `insufficient_data`, `not_found`, `unavailable`, `invalid_request`, and `error` must be returned to the model as explicit states, not converted into fabricated results.
- Keep current clients compatible; no `/chat` request contract break is required.

## Non-Goals

- Do not add write operations, trading operations, wallet access, or marketplace mutations.
- Do not let user text or model-generated arguments choose arbitrary Agent addresses.
- Do not persist raw Marketplace responses into run plans.
- Do not require a live Marketplace call in release verification.

## Requirements

### `SPEC-MARKETPLACE-AI-INTERFACE-001-R1` Current Agent Resolution

- Marketplace tools MUST resolve the Agent address from server-owned `run_context`.
- Accepted context locations are `marketplace_agent.address`, `marketplace_agent.contract_address`, `agent.address`, `agent.contract_address`, top-level `agent_address`, or top-level `contract_address`.
- `chain_id` MAY be resolved from the same server-owned context.
- If no valid current Agent address exists, tools MUST return a structured unavailable result and MUST NOT call Marketplace.

### `SPEC-MARKETPLACE-AI-INTERFACE-001-R2` Context Tool

- `marketplace_agent_context` MUST call `GET /api/v1/agents/{address}/ai-context`.
- The tool MUST support bounded `reports_limit` and `include_raw=false` by default.
- The tool MUST return `agent`, `metrics`, `recent_reports`, and `capabilities` exactly as Marketplace provides them.

### `SPEC-MARKETPLACE-AI-INTERFACE-001-R3` Compute Tool

- `marketplace_agent_compute` MUST call `POST /api/v1/agents/{address}/ai-compute`.
- The tool MUST accept a non-empty list of metric query objects and pass through `window`, `time_range`, `limit`, `query`, and `include_raw` fields.
- Individual result `available`, `status`, `reason`, and `message` fields MUST remain visible to the model.

### `SPEC-MARKETPLACE-AI-INTERFACE-001-R4` Safety And Policy

- Tool permission controls MUST be able to deny both Marketplace tools through `run_context.tool_permissions`.
- Tool errors, timeouts, HTTP failures, and invalid JSON MUST return sanitized structured `unavailable` results.
- The Ask this Agent behavior policy MUST instruct the model to use Marketplace tools for current Agent factual/dynamic data and to say “not supported” or “insufficient data” when Marketplace reports those states.

## Verification

- Focused tests:
  - `tests/test_marketplace_ai_client.py`
  - `tests/test_agent_marketplace_tools.py`
  - affected `tests/test_agent_factory.py`
- Regression tests:
  - `tests/test_tool_context_policy.py`
  - `tests/test_orchestrator.py`
- Harness/release checks:
  - `scripts/check_ai_boundaries.sh`
  - `scripts/check_spec_contract.sh`
  - `scripts/check_harness_workflows.sh`
  - `scripts/verify_release.sh`

## Compatibility

- Existing `/chat` clients continue to work when no Marketplace context is supplied.
- Existing `run_context` masking behavior remains unchanged; only server-provided Agent address fields are used for tool routing.
- Deployments can override `MARKETPLACE_AI_BASE_URL`; the default points at the current documented dev endpoint.
