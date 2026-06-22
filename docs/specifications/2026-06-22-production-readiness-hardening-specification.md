# 2026-06-22 Production Readiness Hardening Specification

## Context

- Spec ID: `SPEC-PROD-READINESS-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- PRD/source request: 用户确认正式认证体系先不做,其余生产化缺口按 Harness Driven Development 补齐,目标是首版 Chat Server 在 DockerHost 上跑真实 GLM-5.2 + Gemini embedding 全流程。
- Target baseline: branch `codex/zai-glm52-dockerhost`, deployed DockerHost smoke commit `ffaa762`.
- Current behavior:
  - Realtime chat、batch worker、Redis Stream replay、provider limiter、secret env/file 注入、RAG pgvector、DockerHost adapter 已具备首版能力。
  - Reaper 只有可调用类,没有服务化调度入口。
  - Metrics 接口默认 no-op,没有 `/metrics` 暴露面或内建采样实现。
  - `/readyz` 只检查 DB 和 event bus 初始化,没有 provider secret/limiter、Redis、reaper 配置、runtime 关键状态。
  - DockerHost worker 使用 `solo --concurrency 1`,适合 smoke correctness,不适合作为生产首版默认。
  - SSE replay gap 目前会作为普通订阅异常返回,没有稳定的 recoverable stream gap 语义。
  - 运行级超时、reaper 调度、负载/发布证据、运维 runbook 尚未形成可执行闭环。
- Problem: 真实 provider 已接通后,系统需要在不做正式 auth 集成的前提下具备生产首版的运行守护、观测、并发、失败收敛、回滚和验证证据。否则“能回答一次”与“可作为线上服务运行”之间仍有明显缺口。
- Non-goals:
  - 不实现正式登录、租户、外部 API key 发放、RBAC 或 OAuth。
  - 不引入 Temporal/DBOS/Prefect 等 durable workflow engine。
  - 不接入真实生产 Prometheus/Grafana 托管服务;本阶段提供 Prometheus 文本出口和 runbook。
  - 不做完整容量压测到最终业务目标;本阶段加入可重复 smoke/load gate。
  - 不改模型供应商、密钥内容或把密钥写入仓库。

## Product Semantics

- User/operator workflow:
  - 普通用户继续通过 `POST /chat` 发起问题,通过 SSE/WS 订阅事件,或 `stream=false` 同步等待最终结果。
  - Operator 可以在 DockerHost 上配置 API、worker、reaper、provider、embedding、provider limits、worker pool/concurrency。
  - Operator 通过 `/readyz` 判断服务是否可接流量,通过 `/metrics` 抓取运行指标,通过 runbook 执行 smoke/load/rollback。
  - Reaper 周期性扫描 stale queued/running runs,对可重试 batch 重新入队,对孤儿 realtime run 标记失败并尽量写 terminal event。
- State model:
  - `agent_run.status` 必须最终进入 `SUCCEEDED|FAILED|CANCELLED`。
  - Reaper 的每次扫描输出 `inspected/requeued/failed/ignored` 指标和日志。
  - Metrics 仅是观测状态,不是业务权威状态。
- Ownership and identity rules:
  - 保留现有 header-derived user identity 和 owner checks。
  - 本规格不扩展正式认证体系。
- Permissions/authentication:
  - `/healthz`, `/readyz`, `/metrics`, docs/openapi 作为平台/探针端点保持公开。
  - 业务端点仍按现有中间件需要 Authorization Bearer 或 X-API-Key。
- Empty, error, retry, timeout, duplicate, and partial-failure behavior:
  - SSE/WS replay cursor 超出 Redis Stream retention 时,返回稳定 `STREAM_GAP` 错误事件/关闭语义,客户端可转轮询 `/runs/{id}` 或重新拉最终状态。
  - Reaper 自身失败不得崩溃主 API;独立 reaper 服务失败应由 DockerHost healthcheck 暴露。
  - Provider limiter 或 secret readiness 不可用时,`/readyz` 返回 `503 not_ready`,不暴露 secret 值。
  - Realtime run 超过配置最大运行时间时应收敛为失败,释放 lease/capacity/conversation lock。
  - Worker 并发可配置;prefork 子进程必须重置 DB pool,避免继承连接。
- Compatibility and migration expectations:
  - `POST /chat`, `ChatAccepted`, SSE event data shape 保持兼容。
  - 新增 `/metrics` 是 additive。
  - DockerHost env var 新增默认值必须保持 mock/local 可启动。

## API / Interface Contract

- Routes, commands, events, jobs, or UI surfaces:
  - `GET /readyz`: 返回 `status` 与 `checks`。新增 checks 只使用状态词或非敏感配置摘要。
  - `GET /metrics`: Prometheus text exposition, content type `text/plain; version=0.0.4; charset=utf-8`。
  - `GET /stream/{agent_run_id}` and `WS /ws/{agent_run_id}`: replay gap emits `ERROR.data.error = "STREAM_GAP"` with sanitized message。
  - CLI/module: `python -m app.tasks.reaper` runs periodic reaper loop。
  - Script: production smoke/load/readiness gate runs bounded checks and writes release artifacts。
- Request fields and validation:
  - No new chat request fields.
  - Reaper env/config:
    - `REAPER_ENABLED`
    - `REAPER_INTERVAL_S`
    - `REAPER_STALE_AFTER_S`
    - `REAPER_MAX_ATTEMPTS`
  - Runtime env/config:
    - `RUN_MAX_RUNTIME_S`
    - `STREAM_MAXLEN`
    - `WORKER_POOL`
    - `WORKER_CONCURRENCY`
    - `METRICS_ENABLED`
- Response/envelope fields and types:
  - `/readyz.checks` may include:
    - `db: ok|error`
    - `redis: ok|error`
    - `event_bus: ok|not_initialized`
    - `provider_secret: mock|configured|missing`
    - `provider_limiter: ok|disabled|unavailable`
    - `reaper: configured|disabled`
  - `/metrics` includes counters/gauges/histograms from in-process registry.
- Status/error codes:
  - `/metrics`: 200 when enabled, 404 when disabled is acceptable only if explicitly configured; default enabled.
  - `/readyz`: 200 ready only when DB, Redis, event bus, required provider secret, provider limiter are healthy.
  - Stream gap: SSE yields `ERROR`; WebSocket sends error payload then closes with policy/internal close.
- Backward compatibility:
  - Existing health checks continue to pass.
  - Existing tests using `InMemoryMetrics` remain valid.

## Data / Schema / Projection Impact

- Tables, indexes, migrations, backfills:
  - No schema migration required for this increment.
- Read models, projections, snapshots, caches:
  - Redis Stream `maxlen` becomes configurable through settings.
  - Reaper uses existing DB tables and Redis run lease keys.
- Rebuild or cleanup operators:
  - Reaper service is the cleanup/recovery operator for stale accepted work.
  - Runbook documents DockerHost rollback and smoke checks.
- Historical data behavior:
  - Existing stale runs can be reaped using current `TaskState.payload` if present.
  - Runs without requeue payload are failed with sanitized reason.
- Performance-sensitive queries or write paths:
  - Reaper scans are bounded by stale window and should not run every request.
  - Metrics collection must not add blocking I/O to hot path.
  - `/metrics` renders current in-process samples only.

## Architecture

- Modules/files expected to change:
  - `app/core/config.py`
  - `app/core/metrics.py`
  - `app/api/lifespan.py`
  - `app/api/main.py`
  - `app/api/middleware.py`
  - `app/api/routers/health.py`
  - `app/api/routers/stream.py`
  - `app/bus/stream_bus.py`
  - `app/runtime/runner.py`
  - `app/tasks/reaper.py`
  - `dockerhost/compose.yaml`
  - `dockerhost/env.example`
  - `dockerhost/template.yaml`
  - `scripts/`
  - `tests/`
  - `docs/`
- Data flow:
  - API lifespan creates shared Redis, StreamBus, metrics registry, provider limiter, realtime runner.
  - Chat hot path emits metrics through injected registry.
  - StreamBus writes to Redis Stream with configured maxlen.
  - Reaper service runs separately in DockerHost and calls `PendingRunReaper.run_once()` on interval.
  - `/readyz` performs short DB/Redis/secret/limiter probes.
  - `/metrics` renders in-process metrics for scrape/log capture.
- Transaction/concurrency boundaries:
  - Reaper uses its own sessions, no request session reuse.
  - Worker prefork uses DB pool reset on child init.
  - Realtime timeout wraps orchestrator call and releases leases/capacity in `finally`.
- Observability/logging/metrics:
  - Counters:
    - `provider_rate_limit_decisions_total`
    - `provider_rate_limit_tokens_reserved_total`
    - `provider_usage_missing_total`
    - `provider_errors_total`
    - `stream_replay_gap_total`
    - `reaper_runs_total`
    - `reaper_requeued_total`
    - `reaper_failed_total`
  - Gauges:
    - `runner_active_runs`
    - `db_streaming_phase_connections`
    - `redis_stream_lag_events`
  - Histograms:
    - `chat_ttft_seconds`
    - `provider_rate_limit_lua_seconds`
    - `db_pool_checkout_seconds`
    - `reaper_run_seconds`
- Rollback strategy:
  - Set `CHAT_RUNTIME_MODE=celery` to avoid realtime path.
  - Set `REAPER_ENABLED=false` or stop reaper service if it misbehaves.
  - Reduce `WORKER_CONCURRENCY=1` or `WORKER_POOL=solo` for correctness fallback.
  - Set `LLM_PROVIDER=mock` and `RAG_ENABLED=false` for provider outage smoke.
  - Redeploy previous Git ref through DockerHost.

## Harness Classification

- Expected gate(s):
  - `HARNESS-SPEC-FIRST-FEATURE`
  - Focused pytest for health/metrics/reaper/stream/runner/DockerHost config.
  - DockerHost template validation.
  - `make verify-release` with `AI_BOUNDARY_APPROVED=1` after owner-approved runtime/deployment edits.
- Performance-sensitive class:
  - Yes. Realtime timeout, worker concurrency, metrics overhead, and Redis Stream retention affect production behavior.
- Whether harness mapping must be extended:
  - No new workflow class required; existing spec-first and release gates apply.
- Required performance evidence:
  - Bounded smoke/load script can produce TTFT/error-rate JSON against a live URL.
  - `/metrics` exposes counters/gauges after smoke.
- Focused verification commands:
  - `.venv/bin/python -m pytest tests/test_production_readiness.py tests/test_pending_reaper.py tests/test_stream_replay.py tests/test_lifespan_runtime_wiring.py tests/test_realtime_runner.py -q`
  - `docker compose -f dockerhost/compose.yaml config`
  - `envctl validate-template --dir /Users/chris/AiProject/general-agent-ai/dockerhost`
- Prerelease-grade verification commands:
  - `AI_BOUNDARY_APPROVED=1 make verify-release`
  - DockerHost live smoke with real Z.AI and Gemini secrets.

## Acceptance Criteria

- Functional:
  - `/readyz` checks DB, Redis, event bus, provider secret readiness, provider limiter, reaper config without leaking secrets.
  - `/metrics` renders in-process counters/gauges/histograms in Prometheus text format.
  - `PendingRunReaper` has a periodic service entrypoint and DockerHost service.
  - DockerHost worker pool/concurrency are configurable and not hard-coded to solo/1.
  - Realtime runner enforces a configurable max runtime and releases resources on timeout.
  - Redis Stream maxlen is configurable.
  - Stream replay retention gaps surface as stable `STREAM_GAP`.
- Edge cases:
  - Reaper dry-run does not mutate state.
  - Reaper loop continues after one failed iteration.
  - Missing real provider secret makes `/readyz` not ready, but mock provider reports `mock`.
  - `/metrics` output redacts secrets by construction; labels must not include token values.
  - Stream gap does not expose Redis internals beyond a sanitized message.
- Compatibility:
  - Auth integration remains out of scope.
  - Existing chat/RAG/Z.AI/Gemini tests remain passing.
  - Existing `/healthz` remains 200 if process is alive.
- Operational:
  - Production runbook names smoke, load, rollback, secret rotation, backup expectations, and residual risks.
  - Release evidence includes focused tests and harness summary.
- Evidence artifacts:
  - Specification and implementation plan.
  - Focused pytest output.
  - DockerHost compose/template validation output.
  - `make verify-release` summary.

## Review Notes

- Open questions:
  - Final production auth/tenant integration remains pending by user decision.
  - Real production Grafana dashboards are external to this repo; this repo supplies metrics and runbook contracts.
  - Final capacity target and provider quotas need operator inputs.
- Accepted assumptions:
  - Header-derived identity is acceptable until upstream integration decides auth.
  - Prometheus text output is enough for first version; managed scraping can be added outside repo.
  - DockerHost reaper can run as a separate service in the same compose stack.
- Rejected alternatives:
  - Rejected leaving reaper as a manual class only.
  - Rejected hard-coded worker `solo --concurrency 1` as production default.
  - Rejected readiness that reports ready while a real provider secret is missing.
  - Rejected logging raw replay/secret/provider exception payloads to clients.
- Reviewer findings and resolution:
  - Pending during implementation.
