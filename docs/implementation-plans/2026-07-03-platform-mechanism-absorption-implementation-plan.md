# Platform Mechanism Absorption Implementation Plan

Spec ID: `SPEC-PLATFORM-MECHANISM-ABSORPTION-001`
Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
Date: 2026-07-03

## Scope

Implement the first absorption batch from `world-cup-chat-server`: provider key pool, route-aware API limiter, and generic run context plumbing. Keep changes narrowly scoped to runtime/API/config/tests/docs.

## Plan

1. Add failing tests for provider key pool parsing, key-pool limiter behavior, selected-key model construction, route-aware entry limiting, and `run_context` hashing/payload propagation.
2. Add `app/runtime/provider_keys.py` with provider-neutral pool parsing and redacted slot reprs.
3. Extend provider limiter dataclasses and in-memory/Redis limiters with key-pool slot selection, aggregate caps, per-key backoff, and selected-key settlement.
4. Wire the provider key pool through lifespan, provider limiter construction, readiness checks, and orchestrator model selection.
5. Make API `RateLimiter` route-aware with hashed identities and fail-open metrics, then pass request path from middleware.
6. Add `run_context` to `ChatRequest`, idempotency hashing, stored plans, realtime/batch payloads, runner requests, task execution, and provider admission estimates.
7. Run focused tests, then repository Harness/preflight checks.
8. Run a code-review pass against the final diff and address any findings before final handoff.

## Test Commands

```bash
.venv/bin/python -m pytest tests/test_provider_key_pool.py tests/test_api_request_rate_limit.py tests/test_chat_routing.py tests/test_agent_factory.py tests/test_lifespan_runtime_wiring.py tests/test_provider_rate_limits.py -q
scripts/check_ai_boundaries.sh
scripts/check_spec_contract.sh
scripts/check_spec_registry.sh
scripts/verify_release.sh
```

## Stop Condition

Stop when the focused tests pass, Harness checks either pass or have an explicit blocker, and code review finds no unresolved correctness issues in the implemented scope.
