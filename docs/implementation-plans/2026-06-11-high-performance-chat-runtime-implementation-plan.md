# 2026-06-11 High Performance Chat Runtime Implementation Plan

## Plan Header

- Specification: `docs/specifications/2026-06-11-high-performance-chat-runtime-specification.md`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Detailed P0 guardrail plan: `docs/implementation-plans/2026-06-11-provider-rate-limit-and-secret-management-implementation-plan.md`
- Architecture: `docs/ARCHITECTURE.md`
- Target branch/baseline: 当前 `general-agent-ai` 工作区。
- Scope summary: 将实时 Chat 默认执行路径从 Celery Worker 迁移到 FastAPI/Async Runner 常驻事件循环; 将事件通道从 Redis Pub/Sub 迁移到 Redis Stream; 补齐 `Last-Event-ID` 回放、首 token 立即 flush、后续 token 聚合、DB 短事务、conversation lock、idempotency、owner 校验、后台路径 reaper、provider/model 全局 Redis Lua RPM/TPM 限流、Secret Manager 注入/脱敏契约、基础可观测性、测试和 Harness 发布证据闭环。
- Out of scope:
  - 完整生产压测平台。
  - Temporal/DBOS 等 durable workflow。
  - 前端 UI 改造。
  - 模型供应商配额申请。
  - 多云 Secret Manager SDK 直接集成。第一阶段实现 env/file 注入抽象, 由部署平台从 Secret Manager 注入。
  - 精确 tokenizer。第一阶段使用保守 token 估算, 后续可替换为 provider-specific tokenizer。
  - 生产级 Prometheus/Grafana 部署, 本计划只落指标采集点和可测试接口。
  - 完整复制 `/Users/chris/AiProject/ai-first-go-template` 的 Go 工具链。只迁移语言无关的 Harness 约束和 Python 等价脚本。

## Reusable Harness Baseline

The reusable ideas from `/Users/chris/AiProject/ai-first-go-template` are process and evidence contracts, not Go-specific code. Apply them to this project before changing the runtime path.

- Tool-neutral enforcement:
  - Mandatory gates live in scripts, Make targets, and CI, not in one Agent-specific prompt.
  - Codex/Claude prompts may wrap scripts, but scripts are the enforcement source.
- Spec contract:
  - Once a PRD/request has been converted into `docs/specifications/`, the Specification is the implementation source of truth.
  - Changes under `app/api`, `app/runtime`, `app/bus`, `app/tasks`, `app/db`, public schemas, migrations/init SQL, or runtime config require a matching Specification or Implementation Plan change unless explicitly exempted.
  - Spec files should use stable `SPEC-*` IDs for behaviors that tests and release evidence can reference.
- AI boundary contract:
  - Add a Python-adapted `.ai-boundaries.yml` and boundary check script.
  - `allowed`: docs/specifications, docs/implementation-plans, tests, non-sensitive examples.
  - `approval_required`: `AGENTS.md`, `.ai-boundaries.yml`, `.github/`, `scripts/`, `app/api/`, `app/runtime/`, `app/bus/`, `app/tasks/`, `app/db/`, `app/core/models.py`, `app/core/schemas.py`, `app/core/events.py`, `requirements.txt`, `docker-compose.yml`.
  - `forbidden`: `.git/`, `.artifacts/`, `.env`, secrets, private keys, production dumps.
- Release evidence:
  - Add `scripts/verify_release.sh` as the single prerelease entrypoint and `make verify-release` as its wrapper.
  - Write evidence into `.artifacts/release/` with logs and a summary JSON.
  - First Python version should run at least: full `pytest -q`, AI boundary check, spec-contract check, secret scan if available, import/smoke check, focused realtime-chat harness tests, focused provider limiter tests, and focused secret management tests once implemented.
- Spec template shape:
  - Keep current high-level Specification file, and optionally add templates under `docs/specifications/_template/`:
    - `behaviors.feature` for externally visible behavior.
    - `invariants.md` for state, idempotency, ownership, and failure convergence rules.
    - `performance.md` for SLO and benchmark/load-smoke commands.
    - `contracts.md` or `contracts.py` for API/event/schema contracts, replacing the Go template's `types.go`.
- Scoped project guidance:
  - Add root `AGENTS.md` if the repo wants instructions checked into source control.
  - Add scoped guidance only for high-risk areas such as `app/db/AGENTS.md`, `app/runtime/AGENTS.md`, and `app/api/AGENTS.md`; avoid duplicating generic rules everywhere.

## Shared Interface Skeletons

These signatures are the cross-step contracts. If implementation discovers a mismatch, update the Specification before changing these contracts.

```python
@dataclass
class RealtimeRunRequest:
    agent_run_id: str
    conversation_id: str
    user_id: str
    trace_id: str
    message: str
    metadata: dict[str, Any]
    accepted_at: float

@dataclass
class RealtimeRunResult:
    agent_run_id: str
    status: RunStatus
    content: str | None = None
    error: str | None = None
    degraded: bool = False

class RealtimeRunner:
    async def run_chat(self, request: RealtimeRunRequest) -> RealtimeRunResult: ...

class StreamBus:
    async def publish(self, run_id: str, event: AgentEvent) -> AgentEvent: ...
    async def replay(self, run_id: str, after_id: str | None) -> AsyncIterator[AgentEvent]: ...
    async def subscribe(self, run_id: str, after_id: str | None = None) -> AsyncIterator[AgentEvent]: ...

class ConversationLock:
    async def acquire(self, conversation_id: str, owner: str, ttl_s: int) -> LockLease | None: ...

class LockLease:
    async def renew(self) -> None: ...
    async def release(self) -> None: ...

class RunLease:
    async def start(self, run_id: str, runner_id: str, ttl_s: int) -> None: ...
    async def renew(self, run_id: str) -> None: ...
    async def release(self, run_id: str) -> None: ...
    async def is_alive(self, run_id: str) -> bool: ...

class IdempotencyStore:
    async def get(self, user_id: str, key: str) -> IdempotencyRecord | None: ...
    async def create(self, user_id: str, key: str, request_hash: str, run_id: str, response: dict[str, Any]) -> IdempotencyRecord: ...

class PendingRunReaper:
    async def run_once(self, *, dry_run: bool = False) -> ReaperResult: ...

@dataclass
class ProviderLimitRequest:
    provider: str
    model: str
    estimated_input_tokens: int
    max_output_tokens: int
    route_type: Literal["realtime", "batch"]
    agent_run_id: str | None = None
    user_id: str | None = None

@dataclass
class ProviderLimitDecision:
    allowed: bool
    reason: Literal["ALLOWED", "RATE_LIMITED", "BACKING_OFF", "CONFIG_MISSING", "UNAVAILABLE"]
    retry_after_ms: int | None = None
    provider_limit_key: str | None = None

@dataclass
class ProviderUsageSettlement:
    provider: str
    model: str
    reserved_tokens: int
    actual_input_tokens: int | None
    actual_output_tokens: int | None
    route_type: Literal["realtime", "batch"]
    agent_run_id: str | None = None

@dataclass
class ProviderUsageDecision:
    settled: bool
    usage_missing: bool = False
    debit_tokens: int = 0
    remaining_tpm: int | None = None

class ProviderRateLimiter:
    async def acquire(self, request: ProviderLimitRequest) -> ProviderLimitDecision: ...
    async def settle_usage(self, settlement: ProviderUsageSettlement) -> ProviderUsageDecision: ...
    async def record_provider_error(self, provider: str, model: str, status_code: int, retry_after_ms: int | None = None) -> None: ...

class SecretProvider:
    def get_secret(self, name: str) -> SecretValue | None: ...
    def validate_required(self, provider: str, model: str) -> None: ...

class Metrics:
    def observe_ttft(self, seconds: float, labels: dict[str, str]) -> None: ...
    def inc_counter(self, name: str, labels: dict[str, str]) -> None: ...
    def set_gauge(self, name: str, value: float, labels: dict[str, str]) -> None: ...
```

## Step 0. Harness Gate Foundation

- Files/modules:
  - `.ai-boundaries.yml`
  - `scripts/check_ai_boundaries.sh` or Python equivalent
  - `scripts/verify_release.sh`
  - `Makefile`
  - optional `.github/workflows/ci.yml`
  - optional `docs/specifications/_template/`
  - optional root/scoped `AGENTS.md`
- Behavior change:
  - Establish a repeatable release gate before runtime migration starts.
  - Preserve the current lightweight developer flow: `make test` remains fast; `make verify-release` becomes prerelease-grade.
  - Spec-contract gate fails when runtime/API/DB behavior changes without a corresponding Specification or Implementation Plan update.
  - Boundary gate fails on forbidden paths and requires explicit approval for sensitive paths.
- Data contract impact:
  - None for API/runtime behavior.
- Tests to add/update:
  - Script smoke test or self-test for boundary matching if practical.
  - Spec-contract smoke can be implemented with shell fixtures or kept as a logged manual gate in the first phase.
- Verification command:
  - `make verify-release`
- Rollback or compatibility note:
  - Harness scripts are additive. If CI is not present, keep local scripts and Makefile target as the source of truth.

## Step 1. 测试骨架和 Harness Fixtures

- Files/modules:
  - `tests/test_stream_bus.py`
  - `tests/test_realtime_runner.py`
  - `tests/test_chat_routing.py`
  - `tests/test_stream_replay.py`
  - `tests/test_idempotency_and_lock.py`
  - `tests/test_pending_reaper.py`
  - `tests/test_provider_rate_limits.py`
  - `tests/test_secret_management.py`
  - `tests/test_worker_provider_limits.py`
  - `tests/test_agent_factory.py` or existing model factory tests
  - existing `tests/test_orchestrator.py`
- Behavior change:
  - 先用测试表达目标行为, 不直接改生产路径。
  - 覆盖 Redis Stream event id、回放、首 token flush、conversation busy、idempotency、DB 不跨 streaming 持有的可观测钩子、provider/model quota gate、secret validation 和脱敏。
  - 统一测试 fake 契约, 避免各步骤重复造不兼容 fixture。
- Data contract impact:
  - 测试中先定义新事件 envelope: `stream_id` 为主排序字段, `seq` 兼容保留。
- Required fakes:
  - `FakeStreamBus`: `publish/replay/subscribe`, 生成 `1-0`, `2-0` 这类 Redis-like stream id, 并把 id 注入 `event.stream_id`。
  - `FakeStreamingModel`: async generator, 可配置 token delta 和每个 delta 的延迟, 至少支持两个 token chunks。
  - `FakeClock`: `now()` + 可控 advance/sleep, 用于聚合窗口测试。
  - `FakeDbSessionTracker`: 记录 checkout/checkin, 暴露 streaming phase active connection 计数。
  - `FakeConversationLock`: 可配置 acquire 成功/失败、TTL、renew、release。
  - `FakeRunLease`: 可配置 start/renew/release/is_alive 和 TTL 过期。
  - `FakeProviderRateLimiter`: 可配置 `ALLOWED` / `RATE_LIMITED` / `BACKING_OFF` / `CONFIG_MISSING`, 支持 `retry_after_ms`, 并记录 realtime 和 batch 调用都经过同一 gate。
  - `FakeSecretProvider`: 支持 env/file-like secret source, 可模拟缺失、存在和读取错误; 断言错误/日志不包含 secret 值。
- Tests to add/update:
  - `test_stream_bus_xadd_and_xrange_replay`
  - `test_stream_replay_starts_after_last_event_id`
  - `test_realtime_runner_releases_db_before_streaming`
  - `test_first_token_flushes_before_aggregation_window`
  - `test_conversation_lock_returns_409_when_busy`
  - `test_idempotency_key_returns_existing_run`
  - `test_pending_reaper_requeues_or_fails_stale_run`
  - `test_provider_bucket_denies_over_rpm_with_retry_after`
  - `test_provider_bucket_denies_over_tpm_with_retry_after`
  - `test_provider_bucket_is_atomic_for_concurrent_callers`
  - `test_realtime_explicit_provider_limit_returns_429_without_run`
  - `test_auto_mode_provider_limit_degrades_to_batch`
  - `test_celery_worker_retries_after_provider_limit`
  - `test_provider_429_sets_shared_backoff`
  - `test_mock_provider_requires_no_secret`
  - `test_real_provider_missing_secret_fails_fast`
  - `test_secret_values_are_redacted_from_errors_and_repr`
- Verification command:
  - `pytest -q tests/test_stream_bus.py tests/test_realtime_runner.py tests/test_chat_routing.py tests/test_stream_replay.py tests/test_idempotency_and_lock.py tests/test_pending_reaper.py tests/test_provider_rate_limits.py tests/test_secret_management.py tests/test_worker_provider_limits.py`
- Rollback or compatibility note:
  - Tests are additive. If implementation scope changes, update Specification before changing tests.

## Step 2. Schema and Data Contract Additions

- Files/modules:
  - `app/core/models.py`
  - `app/core/schemas.py`
  - `app/db/init.sql`
  - `app/db/repositories.py`
  - optional migration script if repo adds migrations later
- Behavior change:
  - Persist idempotency and run-to-assistant-message binding.
  - Store run route/provider/model/usage/degraded metadata without breaking existing fields.
- Data contract impact:
  - Add nullable `message.agent_run_id` or equivalent assistant message binding.
  - Add unique guard for one assistant final message per run where feasible.
  - Add idempotency record with unique `(user_id, idempotency_key)`.
  - Extend `agent_run.plan` or add `meta/result` compatible field for:
    - `route_type`
    - `provider`
    - `model`
    - `provider_limit_key`
    - `usage`
    - `finish_reason`
    - `degraded`
    - `degraded_reason`
    - `retry_after_ms`
  - Extend `tool_call_log` with `attempt`, `started_at`, `finished_at` if backward-compatible.
- Tests to add/update:
  - Repository tests for idempotency insert/get.
  - Repository tests for assistant message uniqueness per run.
  - Schema serialization tests for optional `route_type`.
- Verification command:
  - `pytest -q tests/test_repositories.py tests/test_chat_routing.py`
  - If no repository test file exists yet, include new tests in `tests/test_db_repositories.py`.
- Rollback or compatibility note:
  - Use nullable fields first.
  - Keep existing `ChatAccepted` fields unchanged.
  - Do not remove old seq fields yet.

## Step 3. Redis Stream Event Bus

- Files/modules:
  - new `app/bus/stream_bus.py`
  - `app/bus/event_bus.py`
  - `app/core/events.py`
  - `tests/test_stream_bus.py`
- Behavior change:
  - Add Redis Stream implementation with:
    - `publish(run_id, event) -> stream_id`
    - `replay(run_id, after_id) -> AsyncIterator[AgentEvent]`
    - `subscribe(run_id, after_id) -> AsyncIterator[AgentEvent]`
    - maxlen / TTL support
  - Use Redis Stream id as SSE id and replay cursor.
  - Preserve old `EventBus` contract where possible for tests and migration.
  - `publish()` must inject returned Redis entry id into the event before returning to callers.
  - `replay()` and `subscribe()` must inject Redis entry id into `event.stream_id` while decoding stream entries.
  - `AgentEvent.to_sse()` must use `stream_id` as `id` when present.
- Data contract impact:
  - `AgentEvent` gains `stream_id: str | None`.
  - `seq` remains optional/compatibility only; ordering uses `stream_id`.
  - `TOKEN.data` remains `{"token": "<delta-or-aggregated-text>"}`; aggregation concatenates token deltas into this same field.
- Tests to add/update:
  - XADD returns stream id.
  - XRANGE replay excludes events up to `Last-Event-ID`.
  - Subscribe yields events and terminates on terminal event.
  - Replay gap beyond retention returns explicit recoverable stream gap error/event.
- Verification command:
  - `pytest -q tests/test_stream_bus.py tests/test_event_bus.py`
- Rollback or compatibility note:
  - Keep existing Pub/Sub implementation available behind configuration during migration.
  - Final target is Stream as replay truth.

## Step 4. SSE / WebSocket Stream Replay

- Files/modules:
  - `app/api/routers/stream.py`
  - `app/api/deps.py`
  - `app/api/repos.py`
  - `tests/test_stream_replay.py`
- Behavior change:
  - `GET /stream/{agent_run_id}`:
    - validates current user owns run.
    - reads `Last-Event-ID` header.
    - replays Redis Stream events after cursor.
    - continues with blocking stream read.
  - `WS /ws/{agent_run_id}`:
    - validates token/header maps to owner.
    - supports cursor via query parameter, e.g. `last_event_id`.
  - Terminal events close stream.
- Data contract impact:
  - SSE `id` becomes Redis Stream id string.
  - Existing event JSON remains parseable.
- Tests to add/update:
  - Owner mismatch returns 403 / WS policy close.
  - Replay from `Last-Event-ID` sends only missed events.
  - Stream gap event/error surfaces when cursor expired.
  - Terminal event closes response.
- Verification command:
  - `pytest -q tests/test_stream_replay.py`
- Rollback or compatibility note:
  - If frontend still sends numeric seq, support best-effort fallback during migration only if old Pub/Sub log exists; otherwise return stream gap.

## Step 5. Conversation Lock and Idempotency

- Files/modules:
  - new `app/api/idempotency.py`
  - new `app/runtime/locks.py` or `app/api/locks.py`
  - `app/api/routers/chat.py`
  - `app/db/repositories.py`
  - `tests/test_idempotency_and_lock.py`
- Behavior change:
  - `POST /chat` reads `Idempotency-Key`.
  - Same `(user_id, idempotency_key)` returns existing accepted response.
  - Same `(user_id, idempotency_key)` with different request hash returns 409 idempotency conflict.
  - Same conversation concurrent realtime run returns `409 CONVERSATION_BUSY`.
  - Realtime path acquires conversation lock before writing user message / agent_run; lock failure produces no DB side effects.
  - Conversation lock:
    - TTL > p95 run duration.
    - watchdog renews during streaming.
    - released on success/failure/cancel.
- Data contract impact:
  - Idempotency table/record stores request hash and `agent_run_id`.
  - Lock keys live in Redis: `lock:conversation:{conversation_id}`.
- Tests to add/update:
  - Duplicate key returns same `agent_run_id`.
  - Same key with incompatible request body returns 409 idempotency conflict.
  - Busy conversation returns 409.
  - Busy conversation does not create user message or run row.
  - Lock release on runner failure.
  - Watchdog renewal extends TTL.
- Verification command:
  - `pytest -q tests/test_idempotency_and_lock.py tests/test_chat_routing.py`
- Rollback or compatibility note:
  - If Redis lock unavailable, realtime path should fail closed or degrade to batch based on config; do not allow concurrent same-conversation writes silently.

## Step 6. Realtime Async Runner

- Files/modules:
  - new `app/runtime/runner.py`
  - `app/runtime/orchestrator.py`
  - `app/runtime/deps.py`
  - `app/runtime/adapters.py`
  - `app/api/runner_gateway.py`
  - `tests/test_realtime_runner.py`
- Behavior change:
  - Introduce `RealtimeRunner.run_chat(...)`.
  - Runner flow:
    1. mark run running.
    2. create `run:{agent_run_id}:lease` with `runner_id`, `started_at`, `last_seen_at`.
    3. start heartbeat renewal task.
    4. load history in short DB transaction.
    5. release DB connection before Pydantic AI streaming.
    6. execute `agent.iter()` / `run_stream_events()`.
    7. first TOKEN flushes immediately.
    8. subsequent TOKEN chunks aggregate by time window or count.
    9. publish events to Redis Stream.
    10. write final assistant message/tool calls/run status in final short transaction.
    11. release run lease and conversation lock.
  - Runner exposes local active-run semaphore.
  - Runner cancellation/failure must stop heartbeat, release lock/lease when possible, emit terminal failure, and mark run FAILED.
- Data contract impact:
  - Tool deps include `agent_run_id`, route metadata, event sink, metrics hooks.
  - Assistant final message binds to `agent_run_id`.
  - Reaper uses run lease to detect orphan RUNNING realtime runs.
- Tests to add/update:
  - First token is published before aggregation wait.
  - DB session is not held during streaming using fake session hooks.
  - Runner publishes terminal event and final DB state.
  - Runner failure emits ERROR and finalizes run.
  - Runner cancellation releases conversation lock.
  - Runner heartbeat renews lease during long stream.
  - Expired run lease lets reaper mark orphan RUNNING run failed.
- Verification command:
  - `pytest -q tests/test_realtime_runner.py tests/test_orchestrator.py`
- Rollback or compatibility note:
  - Guard with `CHAT_RUNTIME_MODE=celery|realtime|auto`.
  - In `celery` mode, current worker path remains available.

## Step 6A. Provider Rate Limit and Secret Management P0

- Files/modules:
  - `app/core/config.py`
  - `app/core/secrets.py`
  - `app/runtime/provider_limits.py` or `app/llm/provider_limits.py`
  - `app/runtime/agent_factory.py`
  - `app/runtime/orchestrator.py`
  - `app/runtime/runner.py`
  - `app/api/lifespan.py`
  - `app/api/routers/chat.py`
  - `app/tasks/agent_tasks.py`
  - `app/llm/providers.py`
  - `tests/test_provider_rate_limits.py`
  - `tests/test_secret_management.py`
  - `tests/test_worker_provider_limits.py`
  - `tests/test_agent_factory.py`
- Behavior change:
  - Implement `SPEC-PROVIDER-RATELIMIT-001`:
    - Parse provider/model limit config from settings, e.g. JSON keyed by canonical `(provider, model)`。
    - Use Redis key `ratelimit:provider:{provider}:{model}` and Lua script to reserve RPM and TPM tokens atomically。
    - Add shared backoff key `backoff:provider:{provider}:{model}`; provider 429 records backoff and both realtime/batch honor it。
    - Realtime runner and Celery worker use the same `ProviderRateLimiter` instance or the same Redis-backed implementation。
    - Limit admission happens before the real model call and never per streamed token。
    - After model completion, actual usage must be settled; `actual_total_tokens > reserved_tokens` debits TPM and may create quota debt。
    - Over-reserved tokens are not refunded in first phase。
    - Provider quota wait/backoff must not hold DB connections。
    - Accepted realtime run gate waits once only when retry-after is within `provider_realtime_gate_wait_budget_ms`; otherwise it fails fast with `ERROR stage=provider_rate_limit`。
    - Provider SDK 429/5xx mapping lives at the provider/model wrapper boundary and must call `record_provider_error(...)` before generic terminal error handling。
  - Implement `SPEC-SECRET-MANAGEMENT-001`:
    - Add `SecretProvider` abstraction with env and mounted-file sources。
    - Treat deployment Secret Manager as the source that injects env vars or files; application code only reads the injected location。
    - `llm_provider=mock` requires no secret。
    - Real provider startup/worker init fails fast when required secret is missing。
    - Remove `"not-set"` or equivalent fake key fallback for real provider model construction。
    - Redact secret values from exceptions, repr, logs, metrics, traces, Redis payloads, DB rows, and release artifacts。
    - Centralize `is_mock_provider(...)` / provider identity so chat preflight, orchestrator gate, and worker setup all bypass mock consistently。
- Data contract impact:
  - No Postgres migration required for secrets or quota。
  - `agent_run.plan` or meta may record sanitized provider fields:
    - `provider`
    - `model`
    - `provider_limit_key`
    - `degraded`
    - `degraded_reason`
    - `retry_after_ms`
  - Redis limiter/backoff keys are ephemeral control-plane state。
- Tests to add/update:
  - Provider bucket allows under RPM/TPM。
  - Provider bucket denies over RPM with `retry_after_ms`。
  - Provider bucket denies over TPM with `retry_after_ms`。
  - Concurrent callers cannot oversubscribe bucket。
  - Provider 429 sets shared backoff。
  - Usage settlement debits underestimated output and exposes future quota debt。
  - Accepted realtime gate waits once when retry-after is inside budget, and fails fast when it exceeds budget。
  - Provider exception mapper extracts retry-after/status and records shared backoff。
  - Mock bypass decision is identical across API preflight, orchestrator, and worker。
  - Realtime explicit provider limit returns 429 without creating a realtime run when preflight denial is possible。
  - Auto mode provider limit degrades to batch and records degraded metadata。
  - Celery worker retries based on shared provider limiter decision。
  - Mock provider requires no secret。
  - Real provider missing secret fails fast with sanitized error。
  - File-injected secret works。
  - Model factory does not use `"not-set"` for real provider traffic。
- Verification command:
  - `.venv/bin/python -m pytest tests/test_provider_rate_limits.py tests/test_secret_management.py tests/test_worker_provider_limits.py tests/test_agent_factory.py -q`
  - `.venv/bin/python -m pytest tests/test_chat_routing.py tests/test_realtime_runner.py tests/test_pending_reaper.py -q`
  - `git diff --check`
  - `bash scripts/check_spec_contract.sh`
- Rollback or compatibility note:
  - Local/dev may disable provider limiter explicitly for mock-only work, but production default is enabled and fail closed。
  - Secret validation cannot be bypassed for real providers in production; rollback is to keep `LLM_PROVIDER=mock` or disable real-provider traffic until Secret Manager injection is fixed。
  - The expanded implementation details live in `docs/implementation-plans/2026-06-11-provider-rate-limit-and-secret-management-implementation-plan.md`; this main plan owns the release gate。

## Step 7. Chat Route Selection

- Files/modules:
  - `app/api/routers/chat.py`
  - `app/api/runner_gateway.py`
  - `app/core/schemas.py`
  - `tests/test_chat_routing.py`
- Behavior change:
  - `POST /chat` route selection:
    - `metadata.mode=batch` -> Celery.
    - `metadata.mode=realtime` -> realtime runner or 503/429 if unavailable or provider/model limit denies preflight.
    - `metadata.mode=auto` or absent -> realtime for normal chat, batch for file/long/slow metadata.
    - `metadata.mode=auto` + provider over-limit/backoff -> degrade to batch when configured, recording `degraded_reason=provider_rate_limited`.
  - Response preserves existing envelope and may add `route_type`.
  - Idempotency replay returns the original `ChatAccepted` envelope with current run status when request hash matches.
  - `stream=false`:
    - For realtime: can wait for terminal event with timeout.
    - For batch: returns accepted unless sync wait explicitly supported.
- Data contract impact:
  - `ChatRequest.metadata` semantics defined for route selection.
  - `ChatAccepted.route_type` optional addition if added to schema.
  - Over-limit realtime responses include `Retry-After` when provider limiter supplies `retry_after_ms`.
- Tests to add/update:
  - Normal chat routes realtime.
  - File/long task routes batch.
  - Realtime unavailable returns 503 or degrades per config.
  - Explicit realtime provider over-limit returns `429 PROVIDER_RATE_LIMITED` before unnecessary realtime run creation.
  - Auto provider over-limit routes batch and stores degraded metadata.
  - Existing response fields still present.
- Verification command:
  - `pytest -q tests/test_chat_routing.py tests/test_provider_rate_limits.py`
- Rollback or compatibility note:
  - Feature flag can force all traffic back to Celery while preserving API.

## Step 8. Tool Call Audit and Runtime Deps

- Files/modules:
  - `app/runtime/agent_factory.py`
  - `app/runtime/adapters.py`
  - `app/tools/router.py`
  - `app/db/repositories.py`
  - `tests/test_tools.py`
  - `tests/test_orchestrator.py`
- Behavior change:
  - `AgentDeps` includes `agent_run_id`.
  - Tool execution receives run id and writes `tool_call_log`.
  - Tool start/finish events include enough metadata to audit and display progress.
  - Slow/blocking tools are routed to async/thread/batch policy per tool metadata.
- Data contract impact:
  - `tool_call_log` records attempt/timing/status where available.
- Tests to add/update:
  - Tool call writes audit record.
  - Tool failure writes ERROR status and does not crash full run unless configured.
  - Search/retrieval events remain compatible.
- Verification command:
  - `pytest -q tests/test_tools.py tests/test_orchestrator.py`
- Rollback or compatibility note:
  - Audit write failures are logged and do not block the run, but metrics must count them.

## Step 9. Batch Worker Path and Pending Reaper

- Files/modules:
  - `app/tasks/agent_tasks.py`
  - `app/tasks/celery_app.py`
  - new `app/tasks/reaper.py`
  - `app/tasks/run_store.py`
  - `Makefile`
  - `tests/test_pending_reaper.py`
- Behavior change:
  - Celery queue naming aligns with actual worker commands.
  - `run_agent_task` is batch/offline path, not realtime default.
  - `run_agent_task` checks the shared provider/model limiter before invoking `agent.run()`.
  - Provider limiter `RATE_LIMITED` / `BACKING_OFF` maps to Celery retry using `retry_after_ms`; it must not busy-wait or bypass the Redis bucket.
  - Pending reaper scans stale `PENDING/QUEUED/RUNNING` run/task rows:
    - re-enqueue if safe and attempt budget remains.
    - mark failed when exhausted or invalid.
    - for `RUNNING` realtime runs, check `run:{agent_run_id}:lease`; only mark orphan failed when lease is missing/expired beyond grace window.
    - for active lease, leave run untouched.
  - Makefile worker target consumes actual batch queues.
- Data contract impact:
  - `task_state.attempt` and payload are used by reaper.
  - `agent_run.error` records reaper final failure reason.
- Tests to add/update:
  - Stale queued run re-enqueues.
  - Exhausted attempt marks failed.
  - Provider limit denial schedules retry and does not mark business failure until retry budget is exhausted.
  - Provider backoff set by realtime path is honored by batch worker, and batch-set backoff is honored by realtime path.
  - RUNNING realtime run with live lease is ignored.
  - RUNNING realtime run with expired/missing lease is marked failed and terminal event is written.
  - Successful queued/run rows are ignored.
  - Makefile/queue constants consistency can be covered by a simple config test.
- Verification command:
  - `pytest -q tests/test_pending_reaper.py tests/test_worker_provider_limits.py`
- Rollback or compatibility note:
  - Reaper should support dry-run mode before enabling mutation in production.

## Step 10. Observability and Metrics Hooks

- Files/modules:
  - new `app/core/metrics.py`
  - `app/api/middleware.py`
  - `app/runtime/runner.py`
  - `app/bus/stream_bus.py`
  - `app/db/session.py` or SQLAlchemy event hook module
  - `app/llm/*` / provider wrapper if applicable
  - `app/runtime/provider_limits.py` or `app/llm/provider_limits.py`
  - `app/core/secrets.py`
  - tests for metrics hooks where practical
- Behavior change:
  - Emit metrics:
    - `chat_ttft_seconds`
    - `chat_active_streams`
    - `runner_active_runs`
    - `runner_event_loop_lag_seconds`
    - `redis_stream_lag_events`
    - `redis_connected_clients`
    - `db_pool_checkout_seconds`
    - `db_streaming_phase_connections`
    - `provider_requests_total`
    - `provider_errors_total`
    - `provider_rate_limit_decisions_total`
    - `provider_rate_limit_retry_after_ms`
    - `provider_rate_limit_lua_seconds`
    - `provider_rate_limit_tokens_reserved_total`
    - `provider_rate_limit_tokens_settled_total`
    - `provider_rate_limit_tokens_debt_total`
    - `provider_usage_missing_total`
    - `provider_backoff_active`
    - `provider_secret_validation_total`
    - `conversation_busy_total`
    - `run_stuck_total`
  - Trace spans include request accepted, history read, DB release before streaming, agent start, first token, stream XADD, SSE send, final DB write.
- Data contract impact:
  - None for API; operational metrics contract added.
- Tests to add/update:
  - TTFT metric records first token timing.
  - DB streaming connection gauge remains zero in runner test.
  - Conversation busy increments counter.
  - Provider limiter decisions and backoff metrics are emitted or no-op safe.
  - Provider usage settlement/debt/missing-usage metrics are emitted or no-op safe.
  - Secret validation metrics expose configured/missing/mock state without values.
- Verification command:
  - `pytest -q tests/test_realtime_runner.py tests/test_idempotency_and_lock.py tests/test_provider_rate_limits.py tests/test_secret_management.py`
- Rollback or compatibility note:
  - Metrics should be no-op safe when Prometheus/OTel exporter is not configured.

## Step 11. Full Integration and Compatibility Pass

- Files/modules:
  - all touched modules
  - `docs/API.md` if public SSE id / route_type behavior needs documentation
  - Specification updates if implementation reveals product ambiguities
- Behavior change:
  - End-to-end realtime Chat works through Redis Stream and Pydantic AI without Celery.
  - End-to-end batch Chat still works through Celery.
  - Existing demo mock provider remains usable without external API key.
  - Real-provider configuration is blocked unless required secret source is present and provider limiter is configured.
  - Realtime and batch paths share provider/model quota and backoff state.
- Data contract impact:
  - Public API remains compatible except documented SSE id semantics.
- Tests to add/update:
  - Full `pytest -q`
  - Optional local smoke with Redis/Postgres:
    - seed/init DB
    - run API
    - submit realtime chat
    - subscribe SSE
    - reconnect with `Last-Event-ID`
    - submit batch chat
    - set tiny provider RPM/TPM and verify realtime 429 / auto batch degradation
    - run fake real-provider secret validation with env/file source
- Verification command:
  - `pytest -q`
  - `make up`
  - `make seed`
  - focused curl smoke commands once implementation exists
  - `.venv/bin/python -m pytest tests/test_provider_rate_limits.py tests/test_secret_management.py tests/test_worker_provider_limits.py -q`
- Rollback or compatibility note:
  - `CHAT_RUNTIME_MODE=celery` is rollback path.
  - DB schema additions are backward-compatible.

## Risk Controls

- Public contract risks:
  - SSE `id` changes from numeric seq to Redis Stream id. Mitigation: keep event body compatible and document cursor semantics.
  - Optional `route_type` must not remove existing response fields.
- Security risks:
  - Stream endpoint must enforce run ownership before replay.
  - WebSocket query token must not bypass owner checks.
  - Tool call arguments/results may contain sensitive data; logs must redact.
  - Provider API keys must come from Secret Manager injection through env/file, never from committed files or database rows.
  - Real provider missing secret must fail fast with sanitized error; no `"not-set"` fallback is allowed.
  - Secret values must not appear in logs, traces, metrics, Redis payloads, Postgres rows, events, tests, or release artifacts.
- Migration/rebuild risks:
  - New idempotency and run binding fields must be nullable initially.
  - Unique constraints should be added after data path is stable or guarded by partial indexes.
- Performance risks:
  - Holding DB connections during streaming would break concurrency. Tests and metrics must verify zero long-held DB connections.
  - One Redis `XREAD BLOCK` per SSE may exhaust Redis connections. Capacity must be measured; fan-out remains a follow-up if threshold is hit.
  - Single runner process can become CPU-bound; deploy multiple runner processes and track event loop lag.
  - Provider limiter adds one Redis Lua round trip per model request; do not call it per token.
  - Usage settlement adds one Redis round trip after model completion.
  - Provider quota wait/backoff must not hold DB connections.
  - Accepted realtime wait is bounded by `provider_realtime_gate_wait_budget_ms`; do not wait indefinitely while holding conversation lock or runner slot.
  - Token estimation must be conservative and cheap; exact tokenizer can be a follow-up.
- Deployment/test-branch risks:
  - Need Redis version supporting Streams.
  - Worker queue configuration must match Makefile and deployment manifests.
  - Metrics exporters may not exist locally; must degrade to no-op.
  - API and Worker must point at the same Redis deployment for provider/model quota to be global.
  - Provider limit config must be deployed to both API and Worker processes.
  - Production provider limiter defaults to enabled and fail-closed; local fail-open must be explicit and visible in release evidence.
- Unrelated local changes to avoid:
  - Do not refactor unrelated LLM provider legacy modules unless needed for metrics wrappers.
  - Do not alter README/API contracts beyond documenting new behavior.
  - Do not add real provider secrets, `.env` files, production dumps, or generated artifacts to git.

## Completion Criteria

- Harness gate foundation exists or is explicitly deferred with reason.
- `make verify-release` exists and writes release evidence, even if some production-grade checks are initially no-op/skipped with explicit summary.
- All planned files changed or explicitly deferred.
- Specification still matches implementation.
- Realtime path no longer depends on Celery.
- Batch path still works through Celery.
- Redis Stream is source of SSE/WS replay truth.
- `Last-Event-ID` replay works.
- First token flush is immediate.
- DB connection is not held during streaming.
- Idempotency and conversation lock semantics pass tests.
- Tool calls are audited.
- PENDING reaper handles stale runs.
- Metrics for TTFT, active runs, Stream lag, DB checkout, provider errors are emitted or no-op safe.
- `SPEC-PROVIDER-RATELIMIT-001` passes focused tests: realtime runner and Celery worker share Redis provider/model bucket, RPM/TPM reservation is atomic, and provider 429 creates shared backoff.
- `SPEC-PROVIDER-RATELIMIT-001` passes settlement tests: underestimated output debits TPM quota debt, over-reserved tokens are not refunded in first phase, and future requests observe the debt.
- `SPEC-SECRET-MANAGEMENT-001` passes focused tests: mock provider requires no key, real provider missing key fails fast, env/file-injected secret works, and secret values are redacted.
- Explicit realtime provider over-limit returns `429 PROVIDER_RATE_LIMITED` or documented fail-closed error without unnecessary realtime run side effects when preflight can decide.
- Auto mode provider over-limit can degrade to batch and records degraded metadata.
- No real provider path uses `"not-set"` or equivalent fake API key.
- Accepted realtime gate waits at most one configured budget window, then fails fast if still denied.
- Provider SDK 429/5xx mapping records shared backoff before generic terminal error handling.
- Mock provider bypass is centralized and consistent across API, runner/orchestrator, and worker.
- Focused tests pass.
- Full `pytest -q` passes or blocker is reported.
- Performance smoke evidence is produced before any production rollout.
