# Platform Mechanism Absorption Specification

Spec ID: `SPEC-PLATFORM-MECHANISM-ABSORPTION-001`
Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
Date: 2026-07-03

## Context

`world-cup-chat-server` has grown several runtime mechanisms that are not World Cup-specific and should be absorbed into this async Agent platform. The reusable parts are provider key-pool admission, route-aware API request limiting, and structured run context propagation. World Cup business semantics, paid block names, prediction constants, and URL-level `user_uuid` auth are explicitly out of scope.

## Goals

- Add a provider key pool abstraction that preserves current single-key behavior while allowing per-key quota, per-key backoff, and selected-key settlement for real providers.
- Make API entry limiting route-aware and secret-safe by hashing identities in Redis keys and tagging fail-open metrics by route.
- Add a generic `run_context` envelope to chat requests and carry it through idempotency, stored run plans, realtime/batch payloads, and provider-token admission estimates.

## Non-Goals

- Do not import World Cup domain fields such as `match_id`, `wc2026_context`, paid unlock blocks, recommendation constants, or prediction model parameters.
- Do not replace the repository's authentication model with URL `user_uuid`.
- Do not add conversation anchor persistence in this iteration; that requires a separate DB contract.
- Do not add a full behavior-policy plugin system in this iteration; that needs separate eval fixtures and policy ownership.
- Do not introduce a production deployment contract checker in this iteration; deployment contract work should remain separate from runtime/API code.

## Requirements

### `SPEC-PLATFORM-MECHANISM-ABSORPTION-001-R1` Provider Key Pool

- Settings MUST support `provider_key_pool_file`, `provider_key_pool_scope`, `provider_key_pool_strategy`, and `zai_api_keys_file`.
- A single existing provider key MUST become an implicit one-slot pool so current deployments keep working.
- A provider-specific key file MAY contain newline-separated keys or JSON with `keys`, optional `scope`, `aggregate_rpm`, and `aggregate_tpm`.
- A generic provider pool JSON MUST select entries by `provider:model`.
- Provider key secrets MUST never appear in object reprs, logs, Redis keys, metrics labels, or readiness output.
- Provider admission MUST return the selected `provider_key_id` and secret when a key-pool slot is chosen.
- Usage settlement and provider backoff MUST target the selected slot when `provider_key_id` is present.
- Aggregate quota MUST still cap the whole provider/model pool.

### `SPEC-PLATFORM-MECHANISM-ABSORPTION-001-R2` Route-Aware API Limiter

- API request limiter keys MUST be scoped by normalized route label and hashed identity.
- Raw bearer tokens or API keys MUST NOT be present in Redis limiter keys or fail-open logs.
- Redis failure MUST remain fail-open for API entry limiting, and MUST increment `api_rate_limit_fail_open_total` with the normalized route label.
- Middleware MUST pass the request path as the route scope and keep the existing auth header flow.

### `SPEC-PLATFORM-MECHANISM-ABSORPTION-001-R3` Structured Run Context

- `ChatRequest` MUST accept a generic `run_context: dict[str, Any]`.
- Idempotency hashes MUST include `run_context` so different server-injected context cannot replay the same request.
- API run plans and Celery/realtime payloads MUST include `run_context`.
- Realtime and batch orchestrator entrypoints MUST carry `run_context`.
- Provider preflight and orchestrator provider admission MUST estimate tokens from message, metadata, and `run_context`, not only message text.

## Verification

- Red/green focused tests:
  - `tests/test_provider_key_pool.py`
  - `tests/test_api_request_rate_limit.py`
  - affected `tests/test_chat_routing.py`, `tests/test_agent_factory.py`, `tests/test_lifespan_runtime_wiring.py`, and `tests/test_provider_rate_limits.py`
- Release gates:
  - `scripts/check_ai_boundaries.sh`
  - `scripts/check_spec_contract.sh`
  - `scripts/check_harness_workflows.sh`
  - `scripts/verify_release.sh`

## Deferred Follow-Ups

- Generic conversation anchor contract, likely `anchor_type`/`anchor_key` plus DB uniqueness semantics.
- Context-bound tool permission/masking interface and policy-specific eval fixtures.
- Domain policy plugin/effect-eval pack architecture.
- Root production deployment contract checker aligned with DockerHost release automation.
