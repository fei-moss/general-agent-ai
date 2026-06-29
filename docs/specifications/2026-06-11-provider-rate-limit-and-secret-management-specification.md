# 2026-06-11 Provider Rate Limit and Secret Management Specification

## Context

- Spec ID: `SPEC-PROVIDER-GUARDRAILS-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Primary behavior IDs:
  - `SPEC-PROVIDER-RATELIMIT-001`: provider/model 级全局 RPM/TPM 限流。
  - `SPEC-SECRET-MANAGEMENT-001`: 生产 LLM provider 密钥从 Secret Manager 注入, 不进入仓库、日志或持久化数据。
- PRD/source request: 接真实 LLM 前必须完成两个 P0 门槛:
  - Provider/model 级限流: Redis token bucket, key 形如 `ratelimit:provider:{provider}:{model}`, Lua 原子执行, realtime runner 和 Celery worker 共享同一 bucket, 支持 RPM/TPM 配置, 超限退避并可降级 batch。
  - 密钥管理: 生产 API key 从 Secret Manager 注入, 不进仓库。
- Target baseline: 当前 `general-agent-ai` 工作区, 基于 `docs/specifications/2026-06-11-high-performance-chat-runtime-specification.md` 和 `docs/ARCHITECTURE.md`。
- Current behavior:
  - API 只有 user 级 `RateLimiter`, 没有 provider/model 级全局配额控制。
  - Realtime runner 和 Celery worker 没有共享 provider quota gate。
  - `agent_factory.build_model()` 直接从 `Settings` 读取 provider API key; OpenAI 兼容 provider 在 key 为空时仍可传 `"not-set"`。
  - `.env`、secrets、private keys 已在 AI boundary 中标为 forbidden, 但没有 Secret Manager 注入契约、启动校验或日志脱敏验收。
- Problem:
  - 真实 LLM provider 有 RPM、TPM、并发请求数和 429 backoff 约束。只做 user 级限流会让多用户、多 worker 同时打爆同一个 provider/model quota。
  - batch worker 与 realtime runner 若不共享 provider bucket, 后台重试会和在线请求互相放大 429。
  - 生产密钥若以普通字符串在 settings、日志、错误消息或测试 artifact 中扩散, 会违反 Cloud 审查和上线门槛。
- Non-goals:
  - 不申请或变更供应商配额。
  - 不实现完整成本计费、用户账单或 per-tenant quota。
  - 不强制第一阶段直接接入某个云厂商 SDK。第一阶段要求平台通过 Secret Manager 注入环境变量或挂载文件, 应用侧只定义安全读取契约。
  - 不实现精确 tokenizer。第一阶段允许保守 token 估算, 后续可替换为 provider-specific tokenizer。
  - 不把 provider quota 写入 Postgres; Redis 是控制面, 不是权威业务存储。

## Product Semantics

- User/operator workflow:
  - Operator 在部署层为每个 provider/model 配置 RPM/TPM 和密钥来源。
  - 本地 demo/mock provider 不需要真实密钥, 默认可继续端到端运行。
  - `LLM_PROVIDER != mock` 时, 服务启动或 worker 初始化必须校验所需密钥存在; 缺失时 fail fast, 错误消息只能包含缺失的变量名或 provider/model, 不能包含密钥值。
  - 每一次真实 model call 前必须通过 provider/model admission gate。realtime runner 和 Celery worker 使用同一个 Redis bucket。
  - `metadata.mode=auto` 时, 若 provider bucket 对实时路径不可用或 retry-after 超过实时等待预算, API 可降级到 batch 并返回原有 `202 ChatAccepted` envelope, `route_type=batch`, `degraded=true` 写入 run plan/meta。
  - `metadata.mode=realtime` 显式要求实时且 provider bucket 在受理前已知不可用时, 返回 `429 PROVIDER_RATE_LIMITED` 和 `Retry-After`。
  - batch worker 遇到 provider bucket 超限时, 按 Redis 返回的 `retry_after_ms` 和 Celery 退避策略重试; 不忙等、不绕过 bucket。
- State model:
  - Provider admission decision:
    - `ALLOWED`: 可调用 provider。
    - `RATE_LIMITED`: 未获得 RPM/TPM 预算, 带 `retry_after_ms`。
    - `BACKING_OFF`: provider 429/5xx 设置了全局 backoff, 带 `retry_after_ms`。
    - `CONFIG_MISSING`: provider/model 未配置 quota 或密钥缺失。
  - Realtime request state:
    - before run creation: 可返回 429 或降级 batch。
    - after run accepted: 若实际 model call 被限流, run 必须收敛为 `FAILED` 或按策略发出降级事件, 不允许卡 `RUNNING`。
  - Batch task state:
    - provider 超限不算业务失败; 在 retry budget 内进入 Celery retry。
    - retry budget 耗尽后 run 标记 `FAILED`, error 为 sanitized `PROVIDER_RATE_LIMITED`。
- Ownership and identity rules:
  - Provider bucket 按 canonical `(provider, model)` 隔离, 不按 user 隔离。
  - Provider/model 名称必须规范化为小写、安全字符, 不允许把 user input 直接拼入 Redis key。
  - 用户级限流和 provider/model 限流同时生效; 用户级通过不代表 provider 级通过。
- Permissions/authentication:
  - 无新增用户权限。
  - 运维可通过环境变量配置 limits 和 secret source。
  - 健康检查只能暴露 `configured/missing` 状态, 不暴露密钥值、密钥长度、密钥前后缀。
- Empty, error, retry, timeout, duplicate, and partial-failure behavior:
  - `mock` provider 绕过 provider token bucket 和 secret validation。
  - provider limit Redis 不可用时:
    - production 默认 fail closed, 返回/抛出 `503 PROVIDER_LIMITER_UNAVAILABLE`。
    - local/dev 可通过显式配置 `PROVIDER_LIMIT_FAIL_OPEN=true` fail open; release evidence 必须记录该配置。
  - provider 返回 429:
    - 写入 `backoff:provider:{provider}:{model}` 或等价字段。
    - 后续 realtime/batch 都必须先尊重该 backoff, 不立即重打 provider。
  - provider 返回 5xx:
    - 记录 provider error metric。
    - 可使用较短 backoff, 但不得无限重试。
  - TPM 采用 "pre-reserve + post-settle" 语义:
    - 调用前预留 `estimated_input_tokens + max_output_tokens` 或配置允许的保守 output 预算。
    - 调用结束后必须使用 provider 返回的实际 usage 做对账。
    - 若 `actual_input_tokens + actual_output_tokens > reserved_tokens`, limiter 必须原子扣减差额, 允许 `tpm_tokens` 变成负数作为 quota debt, 后续请求需等 refill 还清后才可继续。
    - 若实际 usage 小于预留, 第一阶段不做 refund; 这是有意选择, 用吞吐换硬保护, 后续可增加安全 refund。
    - 若 provider 未返回 usage, 记录 `usage_missing` metric, 保留预留值, 不做 refund。
    - usage settlement Redis 操作失败时 production fail closed, 当前 run 必须发出脱敏错误并收敛失败, 不能把未对账的真实 provider 调用标成成功。
  - run 受理后在真实 model call gate 被拒时:
    - Runner 可等待一次, 仅当 `retry_after_ms <= PROVIDER_REALTIME_GATE_WAIT_BUDGET_MS`。
    - 等待期间不得持有 DB connection, 但会占用 conversation lock、run lease 和 runner slot, 因此默认预算必须短。
    - 一次等待后仍被拒, 或 `retry_after_ms` 超出预算, realtime run 必须立即发 `ERROR stage=provider_rate_limit` 并收敛为 `FAILED`。
    - 受理后的 realtime run 第一阶段不再隐式改投 batch; auto 降级只发生在 API 创建 run 前的 preflight。
- Compatibility and migration expectations:
  - 现有 `POST /chat` 成功 envelope 不变。
  - 新增错误码不改变已有成功响应字段。
  - mock provider 和本地 smoke 不需要真实 provider key。
  - 原有 `.env` 文件仍不得进入仓库; 可新增 `.env.example` 或 docs 示例, 但只能包含占位符。

## API / Interface Contract

- Routes, commands, events, jobs, or UI surfaces:
  - `POST /chat`:
    - realtime explicit over limit: `429 PROVIDER_RATE_LIMITED`。
    - auto mode over limit: 可路由 batch, `route_type=batch`, run plan/meta 标记 `degraded_reason=provider_rate_limited`。
  - `GET /readyz`:
    - 可扩展 `provider_secrets=configured|missing|mock` 和 `provider_limiter=ok|unavailable`。
    - 不暴露 secret 值。
  - Celery `run_agent_task`:
    - provider 超限时按 `retry_after_ms` 重试。
  - Provider wrapper / Pydantic AI model construction:
    - 每次真实 model call 前经过 provider admission。
- Request fields and validation:
  - `metadata.provider` 和 `metadata.model` 若允许覆盖, 必须经过 allowlist 校验; 第一阶段建议只允许 server-side settings 决定 provider/model。
  - `metadata.mode`: `realtime|batch|auto`, 延续 runtime spec。
- Response/envelope fields and types:
  - `ChatAccepted.route_type` 保持可选字段。
  - `agent_run.plan` 或等价 meta 应记录:
    - `provider`
    - `model`
    - `provider_limit_key`
    - `degraded`
    - `degraded_reason`
    - `retry_after_ms` where applicable
- Status/error codes:
  - `429 PROVIDER_RATE_LIMITED`: provider/model RPM/TPM/backoff 不允许当前实时请求。
  - `503 PROVIDER_LIMITER_UNAVAILABLE`: Redis limiter 不可用且当前环境不允许 fail open。
  - `503 PROVIDER_SECRET_MISSING`: 真实 provider 缺少必要 secret; 通常应在启动时 fail fast, 运行时只作为防御性错误。
- Headers:
  - `Retry-After`: 秒级整数, 从 `retry_after_ms` 向上取整。
  - `X-Provider`: sanitized provider name。
  - `X-Model`: sanitized model name。
  - 不返回任何 secret 信息。
- Events:
  - 超限后若 run 已创建, 可发:
    - `ERROR.data.stage = "provider_rate_limit"`
    - `ERROR.data.error = "PROVIDER_RATE_LIMITED"`
    - `ERROR.data.retry_after_ms`
  - provider 429/5xx 不新增事件类型, 通过 `ERROR` 和 metrics 表达。
- Backward compatibility:
  - 不删除现有 event types。
  - 不改变 `TOKEN.data.token` 形状。

## Data / Schema / Projection Impact

- Tables, indexes, migrations, backfills:
  - 不需要新增 Postgres 表。
  - `agent_run.plan` 或等价 JSON 字段复用现有结构记录 provider/model/limit/degraded 信息。
- Read models, projections, snapshots, caches:
  - Redis provider bucket key:
    - `ratelimit:provider:{provider}:{model}`
  - Redis bucket hash fields:
    - `rpm_tokens`
    - `tpm_tokens`
    - `tpm_debt_tokens` optional derived/diagnostic field when implementation keeps debt separate from negative `tpm_tokens`
    - `last_refill_ms`
    - `updated_at_ms`
    - optional `inflight`
  - Redis backoff key:
    - `backoff:provider:{provider}:{model}`
    - value 至少包含 `retry_after_ms`, `reason`, `set_at_ms`
  - Key TTL:
    - bucket TTL 至少覆盖两个 refill window。
    - backoff TTL 等于 provider 返回或策略计算的 retry-after。
- Rebuild or cleanup operators:
  - 无历史数据 backfill。
  - 可提供运维命令清除某个 provider/model 的 limiter/backoff key, 仅用于误配置恢复。
- Historical data behavior:
  - 旧 run 缺少 provider/model metadata 时不回填。
- Performance-sensitive queries or write paths:
  - provider limiter 不走 Postgres。
  - Lua script 必须一次 round trip 完成 RPM/TPM refill + reserve decision。
  - Usage settlement must be one Redis operation and must not run inside a DB transaction。
  - 不允许每 token 调 limiter; 应按 model request 级别限流。

## Architecture

- Modules/files expected to change:
  - `app/core/config.py`: provider limit 配置、secret source 配置。
  - `app/core/secrets.py`: secret provider abstraction, redaction, required-secret validation。
  - `app/runtime/provider_limits.py` 或 `app/llm/provider_limits.py`: Redis Lua token bucket, decision model, token estimator。
  - `app/runtime/deps.py`: 注入 provider limiter / secret provider。
  - `app/runtime/agent_factory.py`: build real provider model 时使用 secret provider, 不直接读取明文 key 字段。
  - `app/runtime/orchestrator.py`: model call 前执行 provider admission; 记录 metrics/run metadata。
  - `app/api/routers/chat.py`: realtime preflight/backoff 429 或 auto 降级 batch。
  - `app/tasks/agent_tasks.py`: Celery worker provider limit retry。
  - `app/llm/providers.py`: legacy provider wrapper 使用 secret provider 和 limiter, 不打印 key。
  - `tests/`: fake Redis/fake clock/secret fixtures/provider limiter tests。
  - `scripts/verify_release.sh`: 若本地有 secret scanner 则运行; 第一阶段可保持 gitleaks optional, 但必须记录 skip。
  - Data flow:
  - Startup:
    1. Load settings。
    2. Build secret provider from env/file injected by deployment Secret Manager。
    3. If `llm_provider != mock`, validate required secret exists。
    4. Build shared Redis provider limiter。
  - Realtime:
    1. API identifies provider/model and checks hard backoff/limit preflight。
    2. `mode=auto` may degrade to batch before run creation。
    3. Explicit realtime over limit returns 429 before run creation when possible。
    4. Runner/orchestrator gates actual model call with Redis Lua bucket。
  - Batch:
    1. Worker gates actual model call with same Redis Lua bucket。
    2. Rate-limited decision maps to Celery retry countdown。
  - Provider errors:
    1. 429/5xx must be mapped at the provider capability boundary (`app/llm/providers.py` wrapper or model wrapper) because SDK exception types and retry-after fields differ by provider。
    2. Orchestrator/model-call exception handling must call `record_provider_error(...)` for mapped provider throttle/transient errors before emitting terminal run error。
    3. Set Redis backoff key。
    4. Emit metrics and sanitized logs。
  - Transaction/concurrency boundaries:
  - Provider limiter is independent from DB transaction; never hold DB connection while waiting for provider quota.
  - Lua script must atomically refill and reserve RPM/TPM.
  - Realtime preflight is advisory; actual provider call gate is authoritative.
  - Realtime accepted-run gate policy is bounded: wait once only when retry-after is within realtime gate budget, then retry admission once; otherwise fail fast.
  - TPM settlement is authoritative for post-call actual usage; positive usage deltas create future quota debt instead of being ignored.
  - Batch and realtime must share bucket through the same Redis deployment.
  - Observability/logging/metrics:
  - Metrics:
    - `provider_rate_limit_allowed_total{provider,model,route_type}`
    - `provider_rate_limit_denied_total{provider,model,route_type,reason}`
    - `provider_rate_limit_retry_after_ms{provider,model}`
    - `provider_tokens_reserved_total{provider,model}`
    - `provider_tokens_settled_total{provider,model}`
    - `provider_tokens_debt_total{provider,model}`
    - `provider_usage_missing_total{provider,model}`
    - `provider_backoff_active{provider,model}`
    - `provider_secret_missing_total{provider}`
    - existing `provider_requests_total`
    - existing `provider_errors_total`
  - Logs include provider/model/route_type/retry_after_ms/reason, never include secret values。
  - Trace span fields include provider/model and admission decision。
  - Rollback strategy:
  - Feature flag `PROVIDER_RATE_LIMIT_ENABLED=false` may disable limiter in local/dev only。
  - Production default is enabled and fail closed。
  - If limiter causes false positives, route new realtime requests to batch or temporarily reduce provider concurrency; do not bypass secrets validation。
  - If usage settlement causes quota debt from underestimation, reduce max output or provider concurrency before disabling settlement。

## Harness Classification

- Expected gate(s):
  - `ai_boundaries`
  - `spec_contract`
  - full `pytest`
  - focused provider limiter tests
  - focused secret management tests
  - realtime and Celery route smoke with fake limiter
- Performance-sensitive class:
  - Provider limiter is hot path per model request; Redis round trips and Lua cost must be measured。
  - Secret validation is startup/control path, not hot path。
- Whether harness mapping must be extended:
  - Add focused tests for `SPEC-PROVIDER-RATELIMIT-001` and `SPEC-SECRET-MANAGEMENT-001`。
  - Optionally extend `verify_release.sh` with a required local secret pattern check if `gitleaks` is unavailable; otherwise keep gitleaks skip explicit。
- Required performance evidence:
  - Limiter script latency under local Redis smoke。
  - No DB checkout during provider quota wait。
  - Realtime over-limit request returns 429 or degrades before creating unnecessary realtime run。
- Focused verification commands:
  - `.venv/bin/python -m pytest tests/test_provider_rate_limits.py -q`
  - `.venv/bin/python -m pytest tests/test_secret_management.py -q`
  - `.venv/bin/python -m pytest tests/test_chat_routing.py -q`
  - `.venv/bin/python -m pytest tests/test_worker_provider_limits.py -q`
- Prerelease-grade verification commands:
  - `git diff --check`
  - `.venv/bin/python -m pytest -q`
  - `AI_BOUNDARY_APPROVED=1 make verify-release`

## Acceptance Criteria

- Functional:
  - `SPEC-PROVIDER-RATELIMIT-001`: realtime runner and Celery worker both use the same Redis provider/model bucket。
  - `SPEC-PROVIDER-RATELIMIT-001`: RPM and TPM are enforced atomically in Lua。
  - `SPEC-PROVIDER-RATELIMIT-001`: actual provider usage is settled after model call; usage above reservation debits the TPM bucket and creates future quota debt。
  - `SPEC-PROVIDER-RATELIMIT-001`: provider 429 sets shared backoff and subsequent realtime/batch calls honor it。
  - `SPEC-PROVIDER-RATELIMIT-001`: explicit realtime over limit returns 429 before run creation whenever preflight can determine the denial。
  - `SPEC-PROVIDER-RATELIMIT-001`: auto mode can degrade to batch and records degraded metadata。
  - `SPEC-SECRET-MANAGEMENT-001`: `llm_provider=mock` works without secrets。
  - `SPEC-SECRET-MANAGEMENT-001`: `llm_provider=openai|qwen|anthropic|gemini` fails fast when the required secret is missing。
  - `SPEC-SECRET-MANAGEMENT-001`: provider model construction never substitutes `"not-set"` as a fake production API key。
- Edge cases:
  - Concurrent API and worker calls for same provider/model cannot exceed bucket capacity。
  - Underestimated streaming output does not disappear; post-call settlement debits the difference and future calls observe the debt。
  - Accepted realtime run denied at model-call gate waits at most one configured realtime budget window, then fails with sanitized provider rate-limit error。
  - Redis limiter unavailable follows fail-closed by default。
  - Invalid provider/model limit config fails startup with sanitized config error。
  - Secret file path missing fails with sanitized error。
  - Application-authored logs, sanitized exceptions, metrics, and release artifacts do not contain secret values. Third-party SDK traceback content is residual risk at the provider boundary and must be wrapped/redacted before logging.
- Compatibility:
  - Existing mock smoke tests continue to pass。
  - Existing ChatAccepted success envelope is unchanged。
  - Existing user-level rate limiter remains active。
- Operational:
  - Operators can configure limits without code changes。
  - `readyz` or startup logs indicate provider guardrail readiness without exposing secrets。
  - Provider limiter metrics and provider errors are visible to observability pipeline or no-op safe locally。
- Evidence artifacts:
  - Focused provider limiter test logs。
  - Focused secret management test logs。
  - Release summary from `.artifacts/release/summary.json`。

## Review Notes

- Open questions:
  - Exact production RPM/TPM per provider/model must come from vendor quotas and deployment environment。
  - Whether the deployment platform injects secrets as env vars, mounted files, or direct cloud Secret Manager SDK is platform-specific。
  - Exact tokenizer per provider is deferred; first phase uses conservative estimation。
- Accepted assumptions:
  - First phase uses env/file injection as the application contract for Secret Manager.
  - Redis is the cross-process control plane for provider quota。
  - Production limiter fails closed by default。
  - `is_mock` provider bypass is centralized in one helper/registry and reused by chat preflight, orchestrator gate, and worker setup。
  - Post-call usage settlement is required in first phase; refund of over-reserved tokens is deferred。
- Rejected alternatives:
  - Per-process in-memory provider limiter: rejected because it cannot coordinate API and worker replicas。
  - User-only rate limiting: rejected because it does not protect provider/model quotas。
  - Storing provider keys in `.env` committed to repo or database: rejected by secret boundary。
  - Ignoring provider 429 and relying only on Celery retries: rejected because it amplifies provider throttling。
  - Ignoring output-token usage after call: rejected because it turns TPM into a soft estimate under streaming-heavy workloads。
