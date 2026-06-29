# 2026-06-22 Production Readiness Hardening Implementation Plan

## Plan Header

- Specification: `docs/specifications/2026-06-22-production-readiness-hardening-specification.md`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Target branch/baseline: `codex/zai-glm52-dockerhost`
- Scope summary: 在不实现正式认证体系的前提下,补齐 Chat Server 生产首版运行护栏: metrics、readiness、reaper daemon、stream gap、realtime timeout、DockerHost worker/reaper 配置、生产 runbook 和验证 gate。
- Out of scope:
  - 正式 auth/tenant/API-key 集成。
  - 新 DB schema migration。
  - 托管 Prometheus/Grafana 配置。
  - 最终容量压测与 provider quota 调参。

## Change Steps

### 1. Metrics Registry And `/metrics`

- Files/modules:
  - `app/core/metrics.py`
  - `app/api/lifespan.py`
  - `app/api/main.py`
  - `app/api/middleware.py`
  - new or updated tests in `tests/test_production_readiness.py`
- Behavior change:
  - Replace default no-op-only metrics with a process-local registry that can render Prometheus text.
  - Keep `InMemoryMetrics` compatibility for tests.
  - Store registry in `app.state.metrics` and expose `GET /metrics`.
- Data contract impact:
  - Additive endpoint only.
- Tests to add/update:
  - Metrics registry renders counters/gauges/histograms with sanitized labels.
  - `/metrics` is public and returns Prometheus text.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_production_readiness.py -q`
- Rollback or compatibility note:
  - `METRICS_ENABLED=false` can disable the endpoint if needed.

### 2. Readiness Expansion

- Files/modules:
  - `app/core/config.py`
  - `app/api/routers/health.py`
  - `app/api/lifespan.py`
  - `tests/test_production_readiness.py`
- Behavior change:
  - `/readyz` checks DB, Redis ping, event bus initialized, provider secret readiness, provider limiter, and reaper config.
  - Checks expose only status words, no secret values.
- Data contract impact:
  - Additive fields under `checks`.
- Tests to add/update:
  - Mock provider reports `provider_secret=mock`.
  - Real provider with missing secret reports not ready.
  - Redis ping failure returns 503.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_production_readiness.py tests/test_lifespan_runtime_wiring.py -q`
- Rollback or compatibility note:
  - `/healthz` remains process-only.

### 3. Reaper Daemon

- Files/modules:
  - `app/tasks/reaper.py`
  - `dockerhost/compose.yaml`
  - `dockerhost/env.example`
  - `dockerhost/template.yaml`
  - `tests/test_pending_reaper.py`
- Behavior change:
  - Add periodic CLI entrypoint: `python -m app.tasks.reaper`.
  - Add bounded `run_forever` loop with interval, dry-run support, logging, and metrics.
  - Add DockerHost `reaper` service and healthcheck.
- Data contract impact:
  - No schema change; reuses `TaskState.payload` and run leases.
- Tests to add/update:
  - Loop continues after iteration error.
  - Dry-run leaves store unchanged.
  - Metrics increments for inspected/requeued/failed.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_pending_reaper.py -q`
- Rollback or compatibility note:
  - `REAPER_ENABLED=false` or stopping the service disables the daemon.

### 4. Runtime Timeout And Stream Gap

- Files/modules:
  - `app/core/config.py`
  - `app/runtime/runner.py`
  - `app/api/routers/stream.py`
  - `app/bus/stream_bus.py`
  - `tests/test_realtime_runner.py`
  - `tests/test_stream_replay.py`
- Behavior change:
  - Realtime runner wraps orchestrator call with `RUN_MAX_RUNTIME_S`.
  - Timeout returns failed result and existing `finally` releases heartbeat, run lease, conversation lock, and capacity.
  - StreamBus maxlen reads from `STREAM_MAXLEN`.
  - Replay cursor older than retention yields stable `STREAM_GAP`.
- Data contract impact:
  - `ERROR.data.error="STREAM_GAP"` for replay gap.
- Tests to add/update:
  - Runner timeout returns failed result and releases resources.
  - Stream gap is converted to `ERROR` event.
  - StreamBus receives configured maxlen.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_realtime_runner.py tests/test_stream_replay.py tests/test_stream_bus.py -q`
- Rollback or compatibility note:
  - Set higher `RUN_MAX_RUNTIME_S` if legitimate runs exceed first-version budget.

### 5. DockerHost Production Defaults

- Files/modules:
  - `dockerhost/compose.yaml`
  - `dockerhost/env.example`
  - `dockerhost/template.yaml`
  - `Makefile`
  - `scripts/check_dockerhost_production_config.py`
  - `tests/test_production_readiness.py`
- Behavior change:
  - Parameterize worker `WORKER_POOL` and `WORKER_CONCURRENCY`.
  - Add `reaper` service with healthcheck.
  - Add production config check ensuring worker is configurable and reaper exists.
- Data contract impact:
  - DockerHost env var additions only.
- Tests to add/update:
  - Compose file contains worker pool/concurrency env interpolation.
  - Template lists `reaper` service health target.
- Verification command:
  - `docker compose -f dockerhost/compose.yaml config`
  - `.venv/bin/python scripts/check_dockerhost_production_config.py`
- Rollback or compatibility note:
  - Use `WORKER_POOL=solo WORKER_CONCURRENCY=1` for smoke fallback.

### 6. Runbook And Release Evidence

- Files/modules:
  - `docs/PRODUCTION_READINESS_RUNBOOK.md`
  - `scripts/verify_release.sh`
  - `scripts/check_dockerhost_production_config.py`
- Behavior change:
  - Document current chain, smoke/load commands, DockerHost deploy, secret injection, rollback, backup, and residual risks.
  - Add dockerhost production config check to release verification.
- Data contract impact:
  - None.
- Tests to add/update:
  - Script check is part of `make verify-release`.
- Verification command:
  - `AI_BOUNDARY_APPROVED=1 make verify-release`
- Rollback or compatibility note:
  - Documentation and script are additive.

## Risk Controls

- Public contract risks:
  - `/metrics` and `/readyz` are additive; no chat response fields removed.
- Money/accounting/security risks:
  - Metrics labels must not include raw prompts, provider keys, or credentials.
  - Secret readiness reports only `mock|configured|missing`.
- Migration/rebuild risks:
  - No DB migration in this increment.
- Performance risks:
  - Metrics implementation remains in-process and simple; no hot-path network I/O.
  - Reaper interval defaults conservative.
- Deployment/test-branch risks:
  - DockerHost worker default moves from hard-coded `solo/1` to env-configurable prefork/default concurrency; smoke can override to solo.
- Unrelated local changes to avoid:
  - Do not touch credentials or `.artifacts/`.

## Completion Criteria

- Specification still matches implementation.
- Focused tests pass.
- DockerHost compose config and template validation pass.
- `AI_BOUNDARY_APPROVED=1 make verify-release` passes.
- Final answer reports verification and residual risks.
