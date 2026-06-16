# 2026-06-11 High Performance Chat Runtime Specification

## Context

- Spec ID: `SPEC-CHAT-RUNTIME-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Related guardrail IDs:
  - `SPEC-PROVIDER-RATELIMIT-001`: provider/model 级 Redis Lua RPM/TPM 全局限流。
  - `SPEC-SECRET-MANAGEMENT-001`: 生产 LLM provider 密钥从 Secret Manager 注入, 不进入仓库、日志或持久化数据。
- Detailed guardrail spec: `docs/specifications/2026-06-11-provider-rate-limit-and-secret-management-specification.md`。
- PRD/source request: 基于 `docs/ARCHITECTURE.md` 落地高并发、低 TTFT、可水平扩展的 AI Chat 服务。Pydantic AI 只负责单次 Agent 编排, 不承担网关、队列、全局限流、会话持久化或分布式调度。
- Target baseline: 当前 `general-agent-ai` 仓库主工作区。
- Harness reference: `/Users/chris/AiProject/ai-first-go-template` 中可复用的是语言无关的 Harness 方法: Spec-first、AI boundary、tool-neutral release gate、release evidence、scoped AGENTS, 不是 Go 语言实现细节。
- Current behavior: `POST /chat` 创建 conversation/message/run/task 后投递 Celery; Worker 通过同步任务体和 `asyncio.run()` 执行 Pydantic AI orchestration; 事件经 Redis Pub/Sub 推送; SSE/WS 订阅 Pub/Sub; run 事件 seq 由进程内计数器产生。现有热路径只有 user 级限流, 没有 realtime runner 和 Celery worker 共享的 provider/model 配额控制; 真实 provider 密钥读取也缺少 Secret Manager 注入、启动校验和脱敏验收。
- Problem: 实时 Chat 是 I/O-bound 流式负载, 当前 Celery prefork + 每任务事件循环模型会把并发上限绑定到 worker 进程数, 并增加 TTFT; Pub/Sub 无回放和背压; 进程内 seq 多副本不可靠; 文档要求的 SLO 需要明确可验证契约。接真实 LLM 前还必须防止多用户、多进程、多 worker 共同打爆 provider RPM/TPM, 并确保生产 API key 不进入仓库、日志、Redis、Postgres、事件流或 release artifact。
- Non-goals:
  - 不一次性实现完整生产压测环境。
  - 不引入 Temporal/DBOS 等 durable workflow engine。
  - 不改造前端 UI。
  - 不替换 Pydantic AI 作为 Agent 编排层。
  - 不让 Redis 成为最终消息存储。

## Product Semantics

- User/operator workflow:
  - 用户提交 Chat 请求后, 系统根据请求类型选择实时路径或后台路径。
  - 普通短对话默认走实时路径, 用户通过 SSE/WS 接收流式事件。
  - 文件分析、长 RAG、慢工具、批量分析走后台路径, 用户拿 `agent_run_id` 后订阅阶段事件或轮询状态。
  - 如果实时路径容量不足或请求超过实时预算, API 可降级到后台路径并返回 `202 + agent_run_id`。
  - Operator 在部署层配置 provider/model RPM/TPM 和 Secret Manager 注入来源; mock provider 保持零密钥可运行。
  - `LLM_PROVIDER != mock` 时, API 和 Worker 启动必须校验所需 provider secret 已配置, 缺失时 fail fast 且错误脱敏。
  - 每一次真实 model call 前必须经过 provider/model admission gate; realtime runner 和 Celery worker 使用同一个 Redis bucket。
  - `metadata.mode=auto` 且 provider bucket 对实时路径不可用时, API 可降级到 batch 并在 run meta 中记录 `degraded=true` 与 `degraded_reason=provider_rate_limited`。
  - `metadata.mode=realtime` 显式要求实时且 provider bucket 在受理前可确定不可用时, 返回 `429 PROVIDER_RATE_LIMITED` 和 `Retry-After`, 不创建不必要的 realtime run。
- State model:
  - `agent_run.status`: `PENDING -> RUNNING -> SUCCEEDED|FAILED|CANCELLED`。
  - 实时路径可以在 API 事务提交后立即进入 `RUNNING`。
  - 后台路径创建 `PENDING/QUEUED`, Worker 抢占后进入 `RUNNING`。
  - 终止事件为 `RUN_COMPLETED` 或 `ERROR`。
- Ownership and identity rules:
  - conversation、run、stream 均归属于创建它们的 `user_id`。
  - 用户只能读取、续写、订阅自己的 conversation/run。
  - `Idempotency-Key` 按 `(user_id, idempotency_key)` 唯一。
- Permissions/authentication:
  - 除健康检查和文档外, 业务端点必须鉴权。
  - SSE/WS 订阅必须校验 run owner。
  - WebSocket query token 仅作为浏览器兼容输入, 解析后仍映射到 `user_id`。
- Empty, error, retry, timeout, duplicate, and partial-failure behavior:
  - 空 message 返回 422。
  - conversation 不存在返回 404。
  - conversation owner 不匹配返回 403。
  - 实时路径必须先完成 idempotency replay 检查和 conversation lock 获取, 再写 user message / agent_run。
  - 同一 conversation 有运行中的实时 run 时, 第一阶段返回 `409 CONVERSATION_BUSY`, 不做隐式排队, 且不得创建新的 user message / agent_run。
  - 重复 `Idempotency-Key` 且 request hash 相同, 返回原始 `202 ChatAccepted` envelope, 其中 `status` 反映当前 run 状态; 不创建新 run。
  - 重复 `Idempotency-Key` 但 request hash 不同, 返回 409 idempotency conflict。
  - 实时路径失败必须收敛 run 状态为 `FAILED` 或带 `degraded=true` 的成功结果, 不允许卡在 `RUNNING`。
  - 实时路径由内嵌 FastAPI task 或 Async Runner 执行时, 必须维护 run lease / heartbeat; reaper 通过 lease 判断 RUNNING run 是否孤儿化。
  - 后台路径入队失败后不得留下永久悬挂 run; PENDING reaper 负责重新入队或标记失败。
  - provider/model admission decision 包含 `ALLOWED`, `RATE_LIMITED`, `BACKING_OFF`, `CONFIG_MISSING`。`RATE_LIMITED` / `BACKING_OFF` 必须带 `retry_after_ms`。
  - provider 返回 429 时必须写入共享 backoff, 后续 realtime 和 batch 都先尊重 backoff, 不立即重打 provider。
  - provider limiter Redis 不可用时 production 默认 fail closed; local/dev 可显式 `PROVIDER_LIMIT_FAIL_OPEN=true` fail open, release evidence 必须记录该配置。
  - TPM 第一阶段必须执行调用后 usage settlement: 调用前预留保守 token 预算, 调用后用 provider 实际 usage 扣正差额; 若实际大于预留, bucket 可进入负数 quota debt, 后续请求等 refill 还债。
  - usage settlement 失败时 production fail closed; 该 run 必须收敛失败, 不能把未对账的真实 provider 调用标成成功。
  - 受理后的 realtime run 在真实 model-call gate 被拒时, 只允许在 `PROVIDER_REALTIME_GATE_WAIT_BUDGET_MS` 内等待并重试一次; 超出预算或二次拒绝必须立即 `ERROR stage=provider_rate_limit` 并收敛为 `FAILED`。
  - 客户端 SSE/WS 断线后用 `Last-Event-ID` 回放。
- Compatibility and migration expectations:
  - 现有 `POST /chat` 响应 envelope 保持兼容: `conversation_id`, `agent_run_id`, `trace_id`, `status`, `stream_url`, `ws_url`。
  - 现有 SSE/WS 事件类型保持兼容, 但 `id` 从整数 seq 迁移为 Redis Stream id。
  - Celery 保留, 但只作为后台任务执行路径。

## API / Interface Contract

- Routes, commands, events, jobs, or UI surfaces:
  - `POST /chat`: 创建实时或后台 run。
  - `GET /readyz`: 可扩展返回 provider secret/limiter readiness, 只能暴露 `configured|missing|mock|ok|unavailable`, 不暴露 secret 值。
  - `GET /stream/{agent_run_id}`: SSE 事件流, 支持 `Last-Event-ID`。
  - `WS /ws/{agent_run_id}`: WebSocket 事件流, 支持鉴权和终止事件关闭。
  - `GET /runs/{agent_run_id}`: 查询 run 状态。
  - Background job: pending reaper。
  - Background job: batch Celery tasks。
- Request fields and validation:
  - `message`: required, non-empty string。
  - `conversation_id`: optional string; provided 时必须存在且属于当前用户。
  - `stream`: boolean, default true; `true` 表示客户端希望订阅事件流, 不强制执行路径。
  - `metadata`: object; 可包含 `mode=realtime|batch|auto`, `task_type`, `file_refs` 等扩展字段。
  - `metadata.provider` / `metadata.model` 若开放给客户端覆盖, 必须经过 server-side allowlist; 第一阶段建议只允许服务端配置决定 provider/model。
  - `Idempotency-Key`: optional header; 若提供则必须按用户唯一。
- Response/envelope fields and types:
  - `conversation_id: str`
  - `agent_run_id: str`
  - `trace_id: str`
  - `status: RunStatus`
  - `stream_url: str`
  - `ws_url: str`
  - 可扩展 `route_type: realtime|batch`, 但不能破坏现有字段。
  - provider 限流降级时, `agent_run.plan` 或等价 meta 记录 `provider`, `model`, `provider_limit_key`, `degraded`, `degraded_reason`, `retry_after_ms`。
- Status/error codes:
  - 200: 同步或状态查询成功。
  - 202: run accepted。
  - 401: 未鉴权。
  - 403: owner 不匹配。
  - 404: conversation/run 不存在。
  - 409: `CONVERSATION_BUSY` 或 idempotency conflict。
  - 422: 请求校验失败。
  - 429: 用户级限流或 `PROVIDER_RATE_LIMITED`。
  - 503: runner/queue 依赖不可用, `PROVIDER_LIMITER_UNAVAILABLE`, 或 `PROVIDER_SECRET_MISSING`。
  - 504: 同步等待超时。
  - Over-limit realtime responses include `Retry-After` when `retry_after_ms` is available。
- Events:
  - `RUN_STARTED`
  - `PLANNING_STARTED`
  - `RETRIEVAL_STARTED`
  - `RETRIEVAL_FINISHED`
  - `TOOL_CALL_STARTED`
  - `TOOL_CALL_FINISHED`
  - `LLM_GENERATING`
  - `TOKEN`
  - `RESULT_COMPOSED`
  - `RUN_COMPLETED`
  - `ERROR`
- Event envelope:
  - `event_id: str`
  - `agent_run_id: str`
  - `trace_id: str`
  - `type: EventType`
  - `stream_id: str`
  - `ts: float`
  - `data: object`
  - Backward compatibility: `seq` 可保留为兼容字段, 但排序和回放以 `stream_id` 为准。
- Event stream id injection:
  - Event object 在 XADD 前构造时 `stream_id` 允许为 `None`。
  - Stream bus `publish()` 完成 `XADD` 后必须把 Redis entry id 注入返回事件或返回 `(stream_id, event_with_stream_id)`。
  - Stream bus `replay()` / `subscribe()` 从 `XRANGE` / `XREAD` 读取时, 必须把 Redis entry id 注入 `event.stream_id`。
  - `AgentEvent.to_sse()` 必须优先使用 `stream_id` 作为 SSE `id`; 只有兼容旧 in-memory 测试时才允许回退到 `seq`。
- Event data compatibility:
  - `TOKEN.data` 保持现有形状: `{"token": "<delta-or-aggregated-text>"}`。
  - token 聚合时, 将多个 delta 拼接到同一个 `data.token` 字符串, 不改字段名。
  - `RUN_COMPLETED.data` 成功时包含 `{"status": "SUCCEEDED", "content": "<full-answer>"}`。
  - `ERROR.data` 至少包含 `{"stage": "<stage>", "error": "<message>"}`。
  - provider 限流发生在 run 创建后时, `ERROR.data.stage = "provider_rate_limit"`, `ERROR.data.error = "PROVIDER_RATE_LIMITED"`, 并包含脱敏的 `retry_after_ms`。
- Backward compatibility:
  - 前端按 `event` 和 `data` 消费事件的方式保持不变。
  - SSE `id` 从数字变为 Redis Stream id; 前端应原样保存并作为 `Last-Event-ID` 传回。

## Data / Schema / Projection Impact

- Tables, indexes, migrations, backfills:
  - `message` 增加 `agent_run_id nullable` 或新增 assistant message 与 run 的绑定关系; 对 assistant message 建议唯一约束 `(agent_run_id, role)` 或等效约束, 防止重复最终答案。
  - `agent_run` 增加或通过 `plan/meta` 保存 `route_type`, `provider`, `model`, `usage`, `finish_reason`, `degraded`。
  - 新增 idempotency 表或字段:
    - `id`
    - `user_id`
    - `idempotency_key`
    - `agent_run_id`
    - `request_hash`
    - `created_at`
    - unique `(user_id, idempotency_key)`
  - `tool_call_log` 需要真实写入, 并可扩展 `attempt`, `started_at`, `finished_at`。
  - 如需要长期审计, 可新增 `agent_run_event` 里程碑表; 每 token 事件不写 Postgres。
- Read models, projections, snapshots, caches:
  - Redis Stream key: `stream:run:{agent_run_id}`。
  - Run 快速状态 key: `run:{agent_run_id}:status`。
  - Conversation lock key: `lock:conversation:{conversation_id}`。
  - Run lease key: `run:{agent_run_id}:lease`。
  - Provider token bucket key: `ratelimit:provider:{provider}:{model}`。
  - Provider backoff key: `backoff:provider:{provider}:{model}`。
  - Provider usage settlement may keep `tpm_tokens` negative or store an equivalent debt field, but future admission must observe that debt。
  - Runner semaphore key: `semaphore:runner:{runner_group}`。
  - Provider limiter values stay in Redis only and are not authoritative business state。
  - Provider secrets are never stored in Postgres, Redis, events, traces, release artifacts, or test fixtures containing real values。
- Rebuild or cleanup operators:
  - Redis Stream maxlen/TTL cleanup。
  - PENDING reaper: 扫描超时 `PENDING/QUEUED/RUNNING` run, 重新入队或标记失败。
  - Stuck run reaper: 超过 p99 运行预算的 run 进入失败收敛。
- Historical data behavior:
  - 旧 run 没有 idempotency 记录时不回填。
  - 旧事件 seq 仍可显示, 但新回放以 stream id 为准。
- Performance-sensitive queries or write paths:
  - 实时路径读取 history 使用短事务, 读取后立即释放 DB 连接。
  - LLM streaming 期间不得持有 DB session。
  - 最终落库重新获取 DB 连接, 写 assistant message、tool_call_log、agent_run final state。
  - Redis Stream TOKEN 事件首个立即 flush, 后续聚合写入。
  - Provider limiter is called once per model request/admission, never per streamed token。
  - Provider usage settlement is called once after model call completion or failure-with-usage; settlement must not run inside a DB transaction。
  - Waiting for provider quota/backoff must not hold DB connections。

## Architecture

- Modules/files expected to change:
  - `app/api/routers/chat.py`
  - `app/api/routers/stream.py`
  - `app/api/runner_gateway.py`
  - `app/bus/event_bus.py` or new `app/bus/stream_bus.py`
  - `app/runtime/orchestrator.py`
  - new `app/runtime/runner.py`
  - `app/runtime/deps.py`
  - `app/runtime/adapters.py`
  - `app/runtime/provider_limits.py` or `app/llm/provider_limits.py`
  - `app/core/secrets.py`
  - `app/runtime/agent_factory.py`
  - `app/api/lifespan.py`
  - `app/tasks/agent_tasks.py`
  - `app/tasks/celery_app.py`
  - new pending reaper task/module
  - `app/core/events.py`
  - `app/core/models.py`
  - `app/core/schemas.py`
  - `app/db/init.sql`
  - `app/db/repositories.py`
  - `Makefile`
  - tests under `tests/`
- Data flow:
  - Realtime:
    1. API validates auth/body/idempotency。
    2. API ensures conversation ownership。
    3. API acquires conversation lock。
    4. API writes user message and creates agent_run。
    5. Runner writes and renews run lease / heartbeat。
    6. Runner loads history in short DB transaction and releases connection。
    7. Runner checks provider/model admission before the real model call; accepted-run gate denial may wait once only within realtime gate budget; quota wait/backoff does not hold DB connection。
    8. Runner executes Pydantic AI streaming。
    9. Runner settles actual provider usage against the reserved TPM budget。
    10. Runner XADDs events to Redis Stream。
    11. SSE/WS reads Stream and forwards。
    12. Runner writes final DB state and deletes lease。
  - Batch:
    1. API creates run/task。
    2. API enqueues Celery task。
    3. Worker checks the same provider/model Redis bucket before `agent.run()`。
    4. Worker retries with Celery backoff on `RATE_LIMITED` / `BACKING_OFF`。
    5. Worker executes `agent.run()` or staged tasks。
    6. Worker settles actual provider usage against the reserved TPM budget。
    7. Worker writes final DB state and stage events。
    8. Reaper handles stuck PENDING/QUEUED/RUNNING states。
  - Secret management:
    1. Deployment platform injects provider API keys from Secret Manager as env vars or mounted files。
    2. `SecretProvider` resolves env/file source at startup and worker init。
    3. Real provider model construction receives secret values through in-memory wrappers only。
    4. Missing secret fails fast with sanitized error; mock provider bypasses secret validation。
- Transaction/concurrency boundaries:
  - No DB connection held across LLM streaming。
  - Conversation lock guards concurrent writes to conversation history。
  - Conversation lock is acquired before creating the user message/run for realtime path; lock failure returns 409 without DB side effects。
  - Realtime run lease guards orphan detection; missing/expired lease on RUNNING realtime run lets reaper mark FAILED and emit terminal error。
  - Provider token bucket guards model API across all Runner/Worker processes using atomic Lua; RPM and TPM reservation must be one Redis operation。
  - Provider settlement guards underestimated streaming output; positive actual-minus-reserved token deltas must be debited atomically after provider usage is known。
  - Provider SDK 429/5xx mapping belongs at the provider capability/model wrapper boundary, then orchestrator records shared backoff through `record_provider_error(...)` before terminal error handling。
  - Runner local semaphore guards per-process active run count。
  - Celery retry writes must be idempotent。
- New module contracts:
  - `class RealtimeRunner: async def run_chat(self, request: RealtimeRunRequest) -> RealtimeRunResult`
  - `class StreamBus: async def publish(self, run_id: str, event: AgentEvent) -> AgentEvent; async def replay(self, run_id: str, after_id: str | None) -> AsyncIterator[AgentEvent]; async def subscribe(self, run_id: str, after_id: str | None = None) -> AsyncIterator[AgentEvent]`
  - `class ConversationLock: async def acquire(self, conversation_id: str, owner: str, ttl_s: int) -> LockLease | None`
  - `class LockLease: async def renew(self) -> None; async def release(self) -> None`
  - `class RunLease: async def start(self, run_id: str, runner_id: str, ttl_s: int) -> None; async def renew(self, run_id: str) -> None; async def release(self, run_id: str) -> None; async def is_alive(self, run_id: str) -> bool`
  - `class IdempotencyStore: async def get(self, user_id: str, key: str) -> IdempotencyRecord | None; async def create(self, user_id: str, key: str, request_hash: str, run_id: str, response: dict) -> IdempotencyRecord`
  - `class PendingRunReaper: async def run_once(self, *, dry_run: bool = False) -> ReaperResult`
  - `class ProviderRateLimiter: async def acquire(self, request: ProviderLimitRequest) -> ProviderLimitDecision; async def settle_usage(self, settlement: ProviderUsageSettlement) -> ProviderUsageDecision; async def record_provider_error(self, provider: str, model: str, status_code: int, retry_after_ms: int | None = None) -> None`
  - `class SecretProvider: def get_secret(self, name: str) -> SecretValue | None; def validate_required(self, provider: str, model: str) -> None`
  - `class Metrics: def observe_ttft(self, seconds: float, labels: dict) -> None; def inc_counter(self, name: str, labels: dict) -> None; def set_gauge(self, name: str, value: float, labels: dict) -> None`
- Observability/logging/metrics:
  - Prometheus / OpenTelemetry required。
  - TTFT: `first_token_flushed_at - chat.accepted_at`。
  - Runner active runs gauge。
  - event loop lag histogram。
  - Redis Stream lag gauge。
  - Redis connected/blocked clients。
  - DB pool checkout duration histogram。
  - streaming phase active DB connections gauge must remain 0。
  - Provider limiter decisions: allowed/denied/backoff/config-missing counters。
  - Provider limiter Redis Lua latency histogram。
  - Provider tokens reserved counters or histograms for RPM/TPM budgeting。
  - Provider usage settlement/debt/missing-usage counters。
  - Provider 429/5xx counters。
  - Secret validation result counters without values。
  - Stuck run gauge。
  - Logs and traces include `trace_id`, `agent_run_id`, `conversation_id`, `runner_id`, `provider`, `model`, `route_type`, `final_status`。
- Rollback strategy:
  - Feature flag route selection: `CHAT_RUNTIME_MODE=celery|realtime|auto`。
  - If realtime runner fails, route new requests to batch/Celery path while preserving existing API envelope。
  - Provider limiter may be disabled only in local/dev via explicit feature flag; production default is enabled and fail closed。
  - Secret validation cannot be disabled for real providers in production; rollback to `LLM_PROVIDER=mock` or keep real-provider traffic disabled until Secret Manager injection is fixed。
  - Redis Stream event bus can run alongside Pub/Sub during migration if needed, but final target is Stream as source of replay truth。
  - DB migrations must be backward-compatible: nullable fields first, constraints after data path is stable。

## Harness Classification

- Expected gate(s):
  - Harness foundation gate: `.ai-boundaries.yml`, boundary check, spec-contract check, prerelease `verify_release` entrypoint。
  - Unit tests for stream bus, idempotency, locks, route selection, runner lifecycle。
  - Unit tests for provider token bucket, provider backoff, secret provider, and model factory secret validation。
  - Async integration tests for realtime run + SSE replay。
  - DB migration / schema tests。
  - Performance smoke harness for TTFT and active run metrics。
- Spec-contract expectation:
  - The Specification under `docs/specifications/` is the implementation source of truth once written。
  - Runtime/API/DB/schema/config changes require a matching Specification or Implementation Plan update unless explicitly exempted。
  - New externally visible behaviors should carry stable `SPEC-*` IDs in spec/test evidence。
- AI boundary expectation:
  - Allowed-by-default paths should be low-risk docs/tests/specification work。
  - Approval-required paths include scripts, CI, runtime/API/bus/tasks/db/core schema/event files, dependencies, and deployment config。
  - Forbidden paths include `.git/`, `.artifacts/`, `.env`, secrets, private keys, and production dumps。
- Release evidence expectation:
  - `make verify-release` should run the prerelease script and write `.artifacts/release/summary.json` plus logs。
  - First version may mark unavailable production-grade checks as skipped, but skips must be explicit in the summary。
- Performance-sensitive class:
  - Yes. Realtime Chat path is latency and concurrency sensitive。
- Whether harness mapping must be extended:
  - Yes, if repo harness does not already classify realtime streaming, Redis Stream replay, and runner metrics。
- Required performance evidence:
  - TTFT p95 under target in smoke/load environment。
  - No DB connection held during streaming。
  - Redis Stream lag does not grow under smoke load。
  - Runner event loop lag under threshold。
  - First token flush happens before aggregation window。
  - Provider limiter Lua latency under local Redis smoke target。
  - Realtime provider over-limit path returns 429 or degrades before unnecessary realtime run creation。
  - Secret validation evidence shows real providers fail fast when required secret is missing。
- Focused verification commands:
  - `pytest -q tests/test_event_bus.py`
  - `pytest -q tests/test_orchestrator.py`
  - `pytest -q tests/test_provider_rate_limits.py`
  - `pytest -q tests/test_secret_management.py`
  - `pytest -q tests/test_worker_provider_limits.py`
  - New tests for stream replay, runner, idempotency, lock, route selection。
- Prerelease-grade verification commands:
  - Full `pytest -q`。
  - Migration/init smoke using Postgres and Redis。
  - SSE reconnect replay smoke。
  - Lightweight load test for TTFT, active runs, Stream lag, DB pool checkout。
- Required test fakes / fixtures:
  - `FakeStreamBus`: supports `publish`, `replay`, `subscribe`; generates monotonic Redis-like ids such as `1-0`, `2-0`; injects `stream_id` into returned/yielded events; supports retention-gap simulation。
  - `FakeStreamingModel`: async generator model/tool fixture that yields deterministic deltas with controllable delays; must emit at least two token chunks for first-token and aggregation tests。
  - `FakeClock`: injectable monotonic time with `now()` and `sleep()`/advance helpers, used to test token aggregation windows without real sleeps。
  - `FakeDbSessionTracker`: records checkout/checkin and exposes `active_during_streaming`; tests fail if active DB connections are non-zero while streaming。
  - `FakeConversationLock` and `FakeRunLease`: deterministic acquire/renew/release behavior with TTL expiry simulation。
  - `FakeProviderRateLimiter`: deterministic `ALLOWED` / `RATE_LIMITED` / `BACKING_OFF` / `CONFIG_MISSING` decisions with `retry_after_ms`。
  - `FakeSecretProvider`: env/file-like secret source that can assert no secret value appears in error text。

## Acceptance Criteria

- Functional:
  - `POST /chat` can route realtime and batch requests。
  - Realtime path executes Pydantic AI without Celery。
  - SSE/WS reads from Redis Stream。
  - `Last-Event-ID` replays missed events。
  - First TOKEN event flushes immediately。
  - Subsequent TOKEN events are aggregated。
  - Batch path remains available through Celery。
  - PENDING reaper handles stuck queued runs。
  - `SPEC-PROVIDER-RATELIMIT-001`: realtime runner and Celery worker both use the same Redis provider/model bucket。
  - `SPEC-PROVIDER-RATELIMIT-001`: RPM and TPM reservation is atomic and prevents concurrent oversubscription。
  - `SPEC-SECRET-MANAGEMENT-001`: real provider startup/worker init fails fast when required secret is missing; mock provider remains zero-key。
  - `SPEC-SECRET-MANAGEMENT-001`: model factory never uses `"not-set"` or equivalent fake key for real provider traffic。
- Edge cases:
  - Duplicate `Idempotency-Key` returns existing run。
  - Conversation busy returns `409 CONVERSATION_BUSY`。
  - Owner mismatch returns 403 for conversation/run/stream。
  - Redis Stream replay beyond retention is detected and surfaced as recoverable stream gap。
  - Runner cancellation releases conversation lock and finalizes run state。
  - Provider 429 triggers global backoff/limit behavior。
  - Provider limiter Redis outage follows production fail-closed behavior unless local/dev fail-open is explicitly configured。
  - Secret values are redacted from logs, errors, metrics, traces, Redis payloads, Postgres rows, and release artifacts。
- Compatibility:
  - Existing `ChatAccepted` fields preserved。
  - Existing event types preserved。
  - Frontend can continue parsing event `data`; only SSE id semantics move to Redis Stream id。
- Operational:
  - TTFT p95, active streams, active runs, event loop lag, Stream lag, Redis connections, DB checkout duration, provider errors visible in metrics。
  - Provider limiter allowed/denied/backoff/config-missing counts and limiter latency are visible in metrics。
  - Provider secrets readiness is visible only as configured/missing/mock, never as a value。
  - Alert thresholds defined for SLO breach。
  - DB streaming phase connection gauge remains 0。
  - Runner processes can be scaled horizontally。
- Evidence artifacts:
  - `make verify-release` output。
  - `.artifacts/release/summary.json`。
  - AI boundary check result。
  - Spec-contract check result。
  - Test output。
  - Migration result。
  - SSE replay smoke output。
  - Performance smoke summary。
  - Metrics screenshot or exported sample for TTFT and runner active runs。
  - Focused provider limiter and secret management test output。

## Review Notes

- Open questions:
  - Exact production target for concurrent streams may change from the initial 3000 target。
  - Whether realtime runner is embedded in FastAPI first or immediately split into a service needs implementation planning。
  - Redis Stream retention window needs a product/operator decision, based on expected reconnect window。
  - Whether queueing on conversation lock should be added later instead of `409 CONVERSATION_BUSY`。
  - Exact production RPM/TPM per provider/model must come from vendor quotas and deployment environment。
  - Exact Secret Manager delivery mechanism is platform-specific; first phase supports env/file injection contract。
- Accepted assumptions:
  - First phase uses `409 CONVERSATION_BUSY` for same-conversation concurrency.
  - First phase uses Redis Stream as hot replay source and Postgres for final/milestone state.
  - First phase does not guarantee durable mid-agent resume after runner crash.
  - First phase uses conservative token estimation until provider-specific tokenizers are added.
  - First phase requires post-call usage settlement and defers refund of over-reserved tokens.
  - Mock provider bypass is centralized and reused consistently by chat preflight, orchestrator gate, and worker setup.
  - Production provider limiter is enabled and fail-closed by default.
- Rejected alternatives:
  - Rejected realtime default through Celery prefork because it binds concurrency to process count and increases TTFT.
  - Rejected Redis Pub/Sub as replay source because it lacks durable replay and backpressure.
  - Rejected holding DB sessions through streaming because it binds concurrency to DB pool size.
  - Rejected per-process provider limiter because it cannot coordinate API and Worker replicas.
  - Rejected storing provider API keys in repo, Postgres, Redis, or event payloads.
  - Rejected leaving output-token usage unaccounted because streaming-heavy traffic would silently exceed TPM.
- Reviewer findings and resolution:
  - DB connection lifecycle, multi-process runner, Redis connection capacity, first-token flush, lock lease semantics, SLO metrics, Stream retention, PENDING reaper, provider/model global limit, and Secret Manager injection are explicitly included in this specification.
