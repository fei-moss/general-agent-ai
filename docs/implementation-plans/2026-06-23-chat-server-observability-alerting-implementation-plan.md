# 2026-06-23 Chat Server 生产观测与告警体系完善 Implementation Plan

## Plan Header

- Specification: `docs/specifications/2026-06-23-chat-server-observability-alerting-specification.md`
- Spec ID: `SPEC-CHAT-OBSERVABILITY-ALERTING-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Target branch/baseline: `codex/zai-glm52-dockerhost`
- Scope summary: 在不修改 runtime/API/DockerHost 文件的前提下,提交生产观测资产、离线资产 validator、pytest 契约测试,并同步中文 spec、plan、runbook。资产包括 Grafana dashboard JSON、Prometheus alert rules YAML,覆盖请求量、错误率、TTFT、stream token gap、provider 429/5xx、Celery、reaper、readiness。
- Allowed files for this slice:
  - `docs/specifications/2026-06-23-chat-server-observability-alerting-specification.md`
  - `docs/implementation-plans/2026-06-23-chat-server-observability-alerting-implementation-plan.md`
  - `docs/OBSERVABILITY_AND_ALERTING_RUNBOOK.md`
  - `tests/test_observability_alerting_runbook_contract.py`
  - `ops/observability/chat_server_overview_dashboard.json`
  - `ops/observability/chat_server_alert_rules.yml`
  - `scripts/validate_observability_assets.py`
  - `tests/test_observability_assets.py`
- Out of scope:
  - 修改 `app/` runtime、API、metrics、health、tasks、db 或 provider 行为。
  - 修改 DockerHost compose/template/env/deploy/rollback 文件。
  - 修改 `scripts/verify_release.sh`;主线程后续再决定是否把 validator 纳入 release gate。
  - 直接安装生产 Grafana dashboard、Prometheus alert rules 或 Alertmanager route。
  - 查询生产日志、打印 token、写入真实 secret。
  - 执行 deployment、rollback、branch-space 或 envctl 操作。

## Change Steps

### 1. Specification

- Files/modules:
  - `docs/specifications/2026-06-23-chat-server-observability-alerting-specification.md`
- Behavior change:
  - 将 `SPEC-CHAT-OBSERVABILITY-ALERTING-001` 从文档/runbook 切片更新为可提交观测资产切片。
  - 声明 dashboard、alert rules、validator、pytest 的最终交付合同。
  - 保留 `Workflow Class: HARNESS-SPEC-FIRST-FEATURE` 和不修改 runtime/DockerHost 的边界。
- Data contract impact:
  - 无 API、DB、Redis、event 或 provider contract 变更。
- Tests to add/update:
  - 更新 `tests/test_observability_alerting_runbook_contract.py`,断言 spec/plan/runbook 引用新资产、validator 和验证命令。
- Verification command:
  - `.venv/bin/python -m pytest tests/test_observability_alerting_runbook_contract.py tests/test_observability_assets.py -q`
  - `scripts/check_spec_contract.sh`

### 2. Grafana Dashboard Asset

- Files/modules:
  - `ops/observability/chat_server_overview_dashboard.json`
- Behavior change:
  - 提交可导入 Grafana 的 dashboard JSON。
  - Dashboard 使用 Prometheus datasource 变量 `${DS_PROMETHEUS}` 和 `env`/`job` 模板变量。
  - Panels 覆盖:
    - `Request rate`: `chat_requests_total`
    - `API error rate`: `chat_requests_total{status=~"4..|5.."}`
    - `TTFT p95`: `chat_ttft_seconds_last`, `chat_ttft_seconds_sum`, `chat_ttft_seconds_count`
    - `Stream token gap p95`: `chat_stream_token_gap_seconds_last`, `chat_stream_stalls_total`
    - `Provider 429 and 5xx`: `provider_errors_total`, `provider_rate_limit_decisions_total`
    - `Celery queue health`: `celery_queue_depth`, `celery_oldest_queued_age_seconds`, `celery_tasks_total`
    - `Reaper recovery`: `reaper_runs_total`, `reaper_requeued_total`, `reaper_failed_total`, `reaper_inspected_total`
    - `Readiness checks`: `chat_readyz_check`, `up`
- Data contract impact:
  - Dashboard references existing metrics where available and explicitly documents expected production scrape/adapter metric families for stream gap, Celery queue and readiness checks。
  - No runtime metric emission is changed in this slice。
- Tests to add/update:
  - `tests/test_observability_assets.py::test_dashboard_json_has_required_panels_and_prometheus_queries`
  - `scripts/validate_observability_assets.py` structure checks。
- Rollback or compatibility note:
  - Remove the JSON asset if rejected; production Grafana import remains an external owner action。

### 3. Prometheus Alert Rules Asset

- Files/modules:
  - `ops/observability/chat_server_alert_rules.yml`
- Behavior change:
  - 提交 Prometheus alert rules YAML group `chat-server-observability`。
  - Alerts include severity, PromQL expression, duration and `runbook_url` annotations。
  - Required alerts:
    - `ChatServerReadinessDown`
    - `ChatServerHighApiErrorRate`
    - `ChatServerTTFTTooHigh`
    - `ChatServerStreamTokenGapTooHigh`
    - `ChatServerProvider429Spike`
    - `ChatServerProvider5xxElevated`
    - `ChatServerCeleryQueueBacklog`
    - `ChatServerReaperStalled`
    - `ChatServerMetricsScrapeStale`
    - `ChatServerSecretLeakSuspected`
- Data contract impact:
  - Alert rules are repository assets only; loading into Prometheus/Alertmanager is not done here。
- Tests to add/update:
  - `tests/test_observability_assets.py::test_alert_rules_yaml_declares_required_alerts_and_runbook_annotations`
  - `scripts/validate_observability_assets.py` alert block checks。
- Rollback or compatibility note:
  - Revert the YAML asset if thresholds or alert ownership are rejected; no service restart is required by this slice。

### 4. Offline Asset Validator

- Files/modules:
  - `scripts/validate_observability_assets.py`
- Behavior change:
  - 新增零外部依赖 Python CLI,默认从仓库根目录校验 `ops/observability/*`。
  - 校验 dashboard JSON 是否可解析、title/uid/schemaVersion 是否符合合同、必需 panel 和 metric family 是否存在、每个 panel target 是否有 PromQL expression。
  - 校验 alert rules YAML 文本结构是否包含 group、必需 alert、`expr`、`for`、`severity`、`annotations`、`runbook_url` 和必需 metric family。
  - 校验资产中没有明显 secret-like literal,例如 private key marker、raw bearer token、常见 provider/GitHub/Slack token 形状、token assignment、inline credential。
  - 支持 `--root <path>` 方便 pytest 用临时目录构造拒绝案例。
- Data contract impact:
  - 无。
- Tests to add/update:
  - `tests/test_observability_assets.py::test_validator_accepts_committed_observability_assets`
  - `tests/test_observability_assets.py::test_validator_rejects_secret_like_literals_in_assets`
- Verification command:
  - `.venv/bin/python scripts/validate_observability_assets.py`

### 5. Observability And Alerting Runbook

- Files/modules:
  - `docs/OBSERVABILITY_AND_ALERTING_RUNBOOK.md`
- Behavior change:
  - 保持中文 operator/Agent runbook。
  - 补充可提交资产路径、validator 使用方式和验证命令:
    - `ops/observability/chat_server_overview_dashboard.json`
    - `ops/observability/chat_server_alert_rules.yml`
    - `.venv/bin/python scripts/validate_observability_assets.py`
    - `.venv/bin/python -m pytest tests/test_observability_alerting_runbook_contract.py tests/test_observability_assets.py -q`
  - 说明 dashboard/rules 是 repository assets,生产安装、datasource uid、job/env labels 和 Alertmanager routing 由观测 owner 在外部完成。
  - 保持 Grafana MCP bounded `POST /v1/logs`、`line_redacted`、secret redaction、diagnostic path 和 handoff evidence。
- Data contract impact:
  - 无。
- Tests to add/update:
  - 更新 `tests/test_observability_alerting_runbook_contract.py`。

### 6. Pytest Contracts

- Files/modules:
  - `tests/test_observability_alerting_runbook_contract.py`
  - `tests/test_observability_assets.py`
- Behavior change:
  - 文档契约测试读取 spec/plan/runbook 并验证关键合同、资产路径和验证命令。
  - 资产测试读取 dashboard/rules/validator,不依赖网络、Grafana、Prometheus、DockerHost、provider credentials、DB、Redis 或环境变量。
  - Validator rejection test 使用临时目录写入 synthetic secret-like dashboard expression,不写入真实 token/key。
- Data contract impact:
  - 无。
- Verification command:
  - `.venv/bin/python -m pytest tests/test_observability_alerting_runbook_contract.py tests/test_observability_assets.py -q`

## Test Plan

- TDD red baseline:
  - 在资产和 validator 缺失时,新增 tests 失败于缺失 dashboard/rules/validator 和文档未引用资产。
- Focused:
  - `.venv/bin/python scripts/validate_observability_assets.py`
  - `.venv/bin/python -m pytest tests/test_observability_alerting_runbook_contract.py tests/test_observability_assets.py -q`
- Harness/document checks:
  - `scripts/check_spec_contract.sh`
  - `scripts/check_harness_workflows.sh`
- Optional broader gate:
  - `make verify-release`
  - `scripts/verify_release.sh` includes an `observability_assets` gate that runs `.venv/bin/python scripts/validate_observability_assets.py` directly.
- Expected outcome:
  - Validator exits 0 and prints `validated observability assets`。
  - Focused pytest passes without external services。
  - Spec contract recognizes `SPEC-CHAT-OBSERVABILITY-ALERTING-001` and stable `HARNESS-SPEC-FIRST-FEATURE` binding。

## Risk Controls

- Public contract risks:
  - None; no API or event shapes changed。
- Money/accounting/security risks:
  - Highest risk is accidentally committing real credentials or unsafe log-query practices。
  - Mitigation: assets use placeholders/metric names only, validator rejects obvious secret-like literals, runbook prohibits token printing and raw log copying。
- Migration/rebuild risks:
  - None; no schema, Redis, projection or data migration。
- Performance risks:
  - None in runtime; dashboard and alert rules run in external observability systems and use bounded PromQL windows。
- Deployment/test-branch risks:
  - Parallel worker owns DockerHost deployment/rollback; this plan does not edit DockerHost files or invoke envctl。
  - `make verify-release` may include unrelated environment requirements; focused validator and pytest are the required proof for this slice。
- Unrelated local changes to avoid:
  - Do not modify `docs/PRODUCTION_READINESS_RUNBOOK.md`。
  - Do not modify `docs/DOCKERHOST_RELEASE_RUNBOOK.md`。
  - Do not modify `app/core/metrics.py`。
  - Do not modify `app/api/routers/health.py`。
  - Do not modify `tests/test_production_readiness.py`。
  - Do not modify `dockerhost/` files。
  - Do not modify `scripts/verify_release.sh`。
  - Do not stage or revert files from the parallel worker。

## Release And Rollback Risk

- Release readiness:
  - The release artifact is documentation plus committed observability assets and offline validation。
  - Before merging, focused validator, focused pytest and Harness doc checks should pass。
- Rollback:
  - Revert the files listed in `Allowed files for this slice` if the operational guidance or assets are rejected。
  - No service restart, DB rollback, migration rollback or DockerHost release action is required for this slice。
- Residual risks:
  - Exact Grafana datasource UID, Prometheus scrape labels and Alertmanager routing may differ in production; runbook tells owners to bind them during import。
  - Some dashboard panels reference expected production metric families not emitted by current in-process metrics yet, such as `chat_stream_token_gap_seconds`, `celery_queue_depth`, `celery_oldest_queued_age_seconds` and `chat_readyz_check`。
  - Alert thresholds require real traffic baseline tuning after deployment。

## Completion Criteria

- `SPEC-CHAT-OBSERVABILITY-ALERTING-001` exists and includes required observability/alerting/security/asset scope。
- Implementation plan references the spec ID, `HARNESS-SPEC-FIRST-FEATURE`, asset paths, validator and tests。
- Runbook contains Grafana MCP bounded query guidance, dashboard/rules asset usage, validation commands, alerts, diagnostic paths and secret redaction boundary。
- `ops/observability/chat_server_overview_dashboard.json` contains required Prometheus panels。
- `ops/observability/chat_server_alert_rules.yml` contains required alert rules with runbook annotations。
- `scripts/validate_observability_assets.py` validates committed assets and rejects secret-like literals offline。
- Focused pytest passes locally。
- No files outside the allowed slice are modified by this worker。
- Final report lists modified files, validation commands, pass/fail status and residual risk。
