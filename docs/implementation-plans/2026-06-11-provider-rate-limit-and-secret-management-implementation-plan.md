# 2026-06-11 Provider Rate Limit and Secret Management Implementation Plan

## Plan Header

- Specification: `docs/specifications/2026-06-11-provider-rate-limit-and-secret-management-specification.md`
- Related architecture: `docs/ARCHITECTURE.md`
- Related runtime spec: `docs/specifications/2026-06-11-high-performance-chat-runtime-specification.md`
- Target branch/baseline: 当前 `general-agent-ai` 工作区。
- Scope summary: 在接真实 LLM 前补齐两个 P0 guardrails: provider/model 级 Redis Lua RPM/TPM 限流, 以及生产 LLM API key 的 Secret Manager 注入/校验/脱敏契约。Realtime runner 和 Celery worker 必须共享 provider bucket。
- Out of scope:
  - 供应商配额申请。
  - 完整成本计费。
  - 精确 tokenizer。
  - 多云 Secret Manager SDK 直接集成。第一阶段实现 env/file 注入抽象, 由部署平台从 Secret Manager 注入。
  - 前端 UI 改造。

## Change Steps

### Step 0: Spec And Harness Contract

- Files/modules:
  - `docs/specifications/2026-06-11-provider-rate-limit-and-secret-management-specification.md`
  - `docs/implementation-plans/2026-06-11-provider-rate-limit-and-secret-management-implementation-plan.md`
  - `scripts/check_spec_contract.sh` only if gate rules need expansion。
- Behavior change:
  - Introduce `SPEC-PROVIDER-RATELIMIT-001` and `SPEC-SECRET-MANAGEMENT-001` as real LLM onboarding blockers。
- Data contract impact:
  - None。
- Tests to add/update:
  - None in this step。
- Verification command:
  - `git diff --check`
  - `bash scripts/check_spec_contract.sh`
- Rollback or compatibility note:
  - Docs-only; rollback removes the P0 gate definition。

### Step 1: Test Fixtures And Failing Tests First

- Files/modules:
  - `tests/harness_fakes.py`
  - `tests/test_provider_rate_limits.py`
  - `tests/test_secret_management.py`
  - `tests/test_chat_routing.py`
  - `tests/test_worker_provider_limits.py`
  - `tests/test_agent_factory.py` or existing model factory tests。
- Behavior change:
  - Express desired behavior before implementation。
- Data contract impact:
  - None。
- Tests to add/update:
  - `test_provider_bucket_allows_under_rpm_tpm`
  - `test_provider_bucket_denies_over_rpm_with_retry_after`
  - `test_provider_bucket_denies_over_tpm_with_retry_after`
  - `test_provider_bucket_is_atomic_for_concurrent_callers`
  - `test_realtime_explicit_provider_limit_returns_429_without_run`
  - `test_auto_mode_provider_limit_degrades_to_batch`
  - `test_celery_worker_retries_after_provider_limit`
  - `test_provider_429_sets_shared_backoff`
  - `test_provider_usage_settlement_debits_underestimated_output`
  - `test_provider_usage_settlement_allows_negative_tpm_debt`
  - `test_realtime_accepted_gate_waits_once_when_retry_after_within_budget`
  - `test_realtime_accepted_gate_fails_when_retry_after_exceeds_budget`
  - `test_provider_error_mapper_extracts_retry_after_and_sets_backoff`
  - `test_mock_provider_bypass_is_shared_across_runtime_paths`
  - `test_mock_provider_requires_no_secret`
  - `test_real_provider_missing_secret_fails_fast`
  - `test_secret_values_are_redacted_from_errors_and_repr`
  - `test_agent_factory_does_not_use_not_set_api_key_for_real_provider`
- Verification command:
  - `.venv/bin/python -m pytest tests/test_provider_rate_limits.py tests/test_secret_management.py -q`
  - Expected result before implementation: failing for missing modules/behavior。
- Rollback or compatibility note:
  - Tests should be deterministic with fake Redis/fake clock; local Redis integration can be separate。

### Step 2: Configuration And Secret Provider

- Files/modules:
  - `app/core/config.py`
  - `app/core/secrets.py`
  - `app/runtime/agent_factory.py`
  - `app/llm/providers.py`
  - tests from Step 1。
- Behavior change:
  - Add provider limit settings:
    - `provider_rate_limit_enabled: bool = True`
    - `provider_rate_limit_fail_open: bool = False`
    - `provider_rate_limits_json: str = "{}"`
    - optional defaults: `provider_default_rpm`, `provider_default_tpm`, `provider_default_max_concurrency`
    - `provider_realtime_preflight_timeout_ms`
    - `provider_realtime_gate_wait_budget_ms`
    - `provider_realtime_degrade_to_batch: bool = True`
  - Add secret settings:
    - `openai_api_key`, `openai_api_key_file`
    - `anthropic_api_key`, `anthropic_api_key_file`
    - `gemini_api_key`, `gemini_api_key_file`
    - `dashscope_api_key`, `dashscope_api_key_file`
    - `provider_secret_strict: bool = True`
  - Implement `SecretProvider` abstraction:
    - `EnvSecretProvider`
    - `FileSecretProvider`
    - `CompositeSecretProvider`
    - `SecretValue` wrapper or use `pydantic.SecretStr`
  - Implement `validate_provider_secrets(settings, secret_provider)`:
    - no-op for `mock`
    - required for real provider
    - sanitized exceptions only。
  - Remove `"not-set"` fallback for real OpenAI-compatible provider construction。
- Data contract impact:
  - None for API; config contract changes。
- Tests to add/update:
  - Missing key fails for real provider。
  - Mock provider works without key。
  - File secret path works。
  - Error messages do not include actual key。
- Verification command:
  - `.venv/bin/python -m pytest tests/test_secret_management.py tests/test_agent_factory.py -q`
- Rollback or compatibility note:
  - Local mock remains default, so local development remains zero-key。

### Step 3: Redis Provider Token Bucket

- Files/modules:
  - `app/runtime/provider_limits.py` or `app/llm/provider_limits.py`
  - `app/core/config.py`
  - `tests/test_provider_rate_limits.py`
  - optional `tests/test_provider_rate_limits_redis_integration.py`
- Behavior change:
  - Implement:
    - `ProviderLimitConfig`
    - `ProviderLimitRequest`
    - `ProviderLimitDecision`
    - `ProviderUsageSettlement`
    - `ProviderUsageDecision`
    - `RedisProviderRateLimiter`
    - `ProviderIdentity` / centralized `is_mock_provider(...)`
    - `estimate_tokens_for_request(...)`
  - Redis key:
    - `ratelimit:provider:{provider}:{model}`
  - Lua script:
    - atomically refills RPM and TPM tokens by elapsed time
    - checks optional backoff key
    - reserves one request token and estimated token budget
    - returns `allowed`, `retry_after_ms`, `reason`, `remaining_rpm`, `remaining_tpm`
  - Settlement script:
    - atomically refills current TPM state
    - computes `delta = max(0, actual_total_tokens - reserved_tokens)`
    - subtracts positive delta from TPM bucket, allowing negative `tpm_tokens` or equivalent quota debt
    - does not refund over-reserved tokens in first phase
    - records usage-missing metric when actual usage is unavailable
  - Implement provider 429/5xx backoff helper:
    - `set_provider_backoff(provider, model, retry_after_ms, reason)`
    - `get_provider_backoff(...)`
- Data contract impact:
  - Redis hash and backoff keys only。
- Tests to add/update:
  - Under limit allowed。
  - RPM exhausted denied with retry-after。
  - TPM exhausted denied with retry-after。
  - Backoff key denies even when bucket has tokens。
  - Concurrent callers cannot oversubscribe fake/real Redis bucket。
  - Invalid provider/model names are normalized or rejected。
  - Post-call actual usage above reservation debits TPM debt and blocks future calls until refill。
  - Post-call actual usage below reservation does not refund in first phase。
  - Mock bypass helper returns the same decision for API preflight, orchestrator, and worker。
- Verification command:
  - `.venv/bin/python -m pytest tests/test_provider_rate_limits.py -q`
- Rollback or compatibility note:
  - Feature flag can disable locally; production default remains enabled。

### Step 4: Runtime And Pydantic AI Integration

- Files/modules:
  - `app/runtime/deps.py`
  - `app/runtime/orchestrator.py`
  - `app/runtime/agent_factory.py`
  - `app/api/lifespan.py`
  - `app/llm/providers.py`
  - tests。
- Behavior change:
  - Add provider limiter and secret provider to `RuntimeDeps`。
  - Build shared `RedisProviderRateLimiter` in lifespan from shared Redis client。
  - Gate every real model request before provider call。
  - Accepted realtime run gate policy:
    - if `retry_after_ms <= provider_realtime_gate_wait_budget_ms`, sleep once and retry admission once。
    - if retry still denied or retry-after exceeds budget, emit sanitized `ERROR stage=provider_rate_limit` and mark run `FAILED`。
    - do not hold DB connection during wait。
  - Preferred implementation:
    - wrap Pydantic AI `Model` with a `RateLimitedModel` that delegates to the real model after admission。
  - If current Pydantic AI model protocol makes wrapping unsafe:
    - gate immediately before `AgentOrchestrator._run_agent()` as first implementation,
    - document that tool-loop multiple model calls require follow-up wrapper before production real traffic。
  - Record provider/model/admission metadata in run plan/meta。
  - Provider 429/5xx from wrapper sets shared backoff。
  - Provider-specific exception mapping:
    - add mapper/registry at `app/llm/providers.py` or model wrapper boundary。
    - extract `status_code`, `retry_after_ms`, and sanitized reason from SDK exceptions。
    - orchestrator catch blocks must call `record_provider_error(...)` before generic error finalization。
  - After model completion, call `settle_usage(...)` with actual provider usage when available; if usage is missing, emit metric and keep the reservation。
- Data contract impact:
  - `agent_run.plan` gains provider limit metadata。
- Tests to add/update:
  - Orchestrator does not call real model when limiter denies。
  - Provider limiter decision becomes sanitized `ERROR` if run already accepted。
  - Provider 429 sets backoff。
  - Accepted realtime run waits once when retry-after is inside budget and then proceeds on allowed retry。
  - Accepted realtime run fails immediately when retry-after exceeds budget。
  - Provider exception mapper records shared backoff before terminal error。
  - Usage settlement debits underestimated output after call。
  - Metrics are emitted/no-op safe。
- Verification command:
  - `.venv/bin/python -m pytest tests/test_orchestrator.py tests/test_provider_rate_limits.py -q`
- Rollback or compatibility note:
  - Mock model bypass keeps existing smoke stable。

### Step 5: API Realtime Preflight And Batch Degrade

- Files/modules:
  - `app/api/routers/chat.py`
  - `app/api/lifespan.py`
  - `app/core/schemas.py` if response needs explicit degraded field; prefer run plan/meta first。
  - tests。
- Behavior change:
  - Resolve canonical provider/model for a chat request from server-side settings and safe metadata allowlist。
  - Preflight provider backoff/limit before creating realtime run where possible。
  - Explicit realtime:
    - denial returns `429 PROVIDER_RATE_LIMITED`, no conversation/user message/run side effects。
  - Auto mode:
    - denial may route to batch and return existing `ChatAccepted` with `route_type=batch`。
    - run plan records `degraded=true`, `degraded_reason=provider_rate_limited`, `retry_after_ms`。
  - Batch explicit:
    - API accepts and worker handles retry。
- Data contract impact:
  - No successful envelope break。
  - Optional degraded metadata in run plan。
- Tests to add/update:
  - Realtime explicit over limit returns 429 and does not create run。
  - Auto over limit creates batch run/task。
  - Idempotency replay still works across degraded batch response。
  - Provider limiter unavailable returns 503 unless fail-open config enabled。
- Verification command:
  - `.venv/bin/python -m pytest tests/test_chat_routing.py tests/test_provider_rate_limits.py -q`
- Rollback or compatibility note:
  - If preflight is too conservative, disable auto-degrade while keeping provider gate at actual model call。

### Step 6: Celery Worker Integration

- Files/modules:
  - `app/tasks/agent_tasks.py`
  - `app/runtime/orchestrator.py`
  - `app/runtime/deps.py`
  - tests。
- Behavior change:
  - Worker builds/uses same Redis provider limiter。
  - Rate-limited decision maps to `self.retry(countdown=retry_after_s)` within existing retry budget。
  - Retry reason is sanitized。
  - Worker respects provider backoff before calling real model。
- Data contract impact:
  - Task result may include sanitized `PROVIDER_RATE_LIMITED` after retry budget exhausted。
- Tests to add/update:
  - Worker retries on limiter denial。
  - Worker does not call provider when denied。
  - Retry countdown respects `retry_after_ms` cap/floor。
- Verification command:
  - `.venv/bin/python -m pytest tests/test_worker_provider_limits.py -q`
- Rollback or compatibility note:
  - Existing batch queue names unchanged。

### Step 7: Observability And Release Guardrails

- Files/modules:
  - `app/core/metrics.py`
  - `app/runtime/provider_limits.py`
  - `app/core/secrets.py`
  - `scripts/verify_release.sh`
  - optional `scripts/check_no_plaintext_provider_keys.sh`
  - tests。
- Behavior change:
  - Emit provider limiter metrics:
    - allowed/denied totals
    - retry-after histogram/gauge
    - tokens reserved
    - active backoff
  - Emit secret validation metrics without values。
  - Add optional local secret grep if `gitleaks` unavailable, scanning for obvious provider key patterns in tracked files only。
- Data contract impact:
  - Release summary may include secret scan status。
- Tests to add/update:
  - Metrics no-op safe。
  - Redaction helper strips configured fake key from logs/errors。
- Verification command:
  - `.venv/bin/python -m pytest tests/test_secret_management.py tests/test_provider_rate_limits.py -q`
  - `AI_BOUNDARY_APPROVED=1 make verify-release`
- Rollback or compatibility note:
  - Secret scan should not block on missing external tools unless a built-in fallback is implemented。

### Step 8: Local Integration Smoke

- Files/modules:
  - `scripts/benchmark_realtime_ttft.py` optional use only。
  - no production code unless a bug is found。
- Behavior change:
  - Validate guardrails against local Redis/Postgres with mock and fake real-provider configuration。
- Data contract impact:
  - None。
- Tests to add/update:
  - Optional local Redis integration test for Lua script。
- Verification command:
  - `make seed`
  - `RATE_LIMIT_PER_MIN=100000 REALTIME_RUNNER_MAX_CONCURRENCY=5000 LOG_LEVEL=WARNING .venv/bin/python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8012 --workers 4 --no-access-log`
  - `.venv/bin/python scripts/benchmark_realtime_ttft.py --base-url http://127.0.0.1:8012 --requests 60 --concurrency 60`
  - focused over-limit HTTP smoke with a tiny RPM/TPM config。
- Rollback or compatibility note:
  - Stop uvicorn after smoke; do not leave local worker/API running。

## Risk Controls

- Public contract risks:
  - Do not alter existing successful `ChatAccepted` fields。
  - New 429/503 details must be stable and documented。
- Money/accounting/security risks:
  - Never log API key values。
  - Do not store provider keys in Postgres, Redis, events, traces, release artifacts, or tests。
  - Provider quota fail-open is forbidden by default in production。
  - Third-party SDK exceptions may contain sensitive implementation details; application logs must use sanitized wrapper exceptions and treat raw SDK traceback as residual risk not to be logged verbatim。
- Migration/rebuild risks:
  - No Postgres migration required。
  - Redis keys are ephemeral and can be cleared if misconfigured。
- Performance risks:
  - Provider limiter adds one Redis Lua round trip per model request。
  - Usage settlement adds one Redis round trip after model completion。
  - Do not call limiter per token。
  - Token estimation must be cheap and deterministic。
  - Realtime accepted-run wait is bounded by `provider_realtime_gate_wait_budget_ms`; never wait indefinitely while holding conversation lock/runner slot。
- Deployment/test-branch risks:
  - Real provider deployment must include Secret Manager injection before `LLM_PROVIDER` is switched from `mock`。
  - Worker and API must use the same Redis deployment for quotas。
  - Provider limit config must be deployed to both API and worker processes。
- Unrelated local changes to avoid:
  - Do not refactor unrelated RAG/tool logic。
  - Do not replace Pydantic AI。
  - Do not commit `.env`, real API keys, production dumps, or generated release artifacts。

## Completion Criteria

- Specification still matches implementation。
- `SPEC-PROVIDER-RATELIMIT-001` focused tests pass。
- `SPEC-PROVIDER-RATELIMIT-001` usage settlement tests pass, including underestimated output debt。
- `SPEC-SECRET-MANAGEMENT-001` focused tests pass。
- Realtime explicit over-limit path returns 429 without run side effects。
- Auto over-limit path degrades to batch where configured。
- Celery worker retries based on shared provider bucket。
- Accepted realtime gate waits only within configured budget and otherwise fails fast。
- Provider 429/5xx exception mapping records shared backoff before generic terminal error handling。
- Real provider missing secret fails fast with sanitized error。
- Mock provider remains zero-key and all existing smoke tests pass。
- `git diff --check` passes。
- Full `.venv/bin/python -m pytest -q` passes。
- `AI_BOUNDARY_APPROVED=1 make verify-release` passes or reports a concrete blocker。
- Release notes state whether provider rate limiter is enabled, fail-open is disabled, and secret scanner status。
