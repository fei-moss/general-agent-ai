# 2026-06-23 Chat Server 生产观测与告警体系完善 Specification

## Context

- Spec ID: `SPEC-CHAT-OBSERVABILITY-ALERTING-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Related specifications:
  - `SPEC-PROD-READINESS-001`: 生产 readiness、metrics、reaper、DockerHost smoke/load/runbook 基础。
  - `SPEC-CHAT-RUNTIME-001`: realtime/batch Chat Server runtime 边界。
  - `SPEC-PROVIDER-GUARDRAILS-001`: provider/model quota、usage settlement、secret readiness。
  - `SPEC-ASYNC-CHAT-ONLY-001`: Chat 接口只接受异步流式合同。
  - `SPEC-INTERNAL-RAG-BOUNDARY-001`: RAG 内部管理边界。
- PRD/source request: 实现“Chat Server 生产观测与告警体系完善”切片,先补稳定 SPEC-* 与 Workflow Class,再补 implementation plan,再补可执行/可校验交付物。最终交付必须包含本 spec、implementation plan、观测告警 runbook、Grafana dashboard JSON、Prometheus alert rules YAML、离线资产 validator 和 pytest 契约测试。
- Target baseline: branch `codex/zai-glm52-dockerhost` 当前工作树;本切片不修改 DockerHost 发布/回滚文件,避免影响并行 worker。
- Current behavior:
  - `docs/PRODUCTION_READINESS_RUNBOOK.md` 已描述 Chat 请求链路、DockerHost deploy、readiness/metrics smoke、load smoke、rollback、backup 和 residual risks。
  - `app/core/metrics.py` 提供 in-process counters、gauges、histogram summaries,并可渲染 Prometheus text。
  - `app/api/routers/health.py` 暴露 `/healthz`、`/readyz`、`/metrics`;`/readyz` 覆盖 DB、Redis、event bus、provider secret、provider limiter、reaper 配置状态。
  - `tests/test_production_readiness.py` 已用 pytest 断言 Prometheus 输出、metrics endpoint、readyz 状态和 DockerHost production config check。
  - Grafana MCP 生产日志访问属于授权运维能力,凭据只在本机私有目录或安全运行环境注入,不得进入仓库。
- Problem: 现有 readiness 和 metrics 面已经存在,但生产使用者仍缺一份可执行的观测/告警合同:核心面板缺少统一口径,日志查询缺少 bounded 查询模板,告警阈值和排障路径缺少可复用流程,secret/token 脱敏边界缺少文档契约测试防退化,并且仓库中缺少可提交、可离线校验的 dashboard/rules 资产供生产安装流程复用。
- Non-goals:
  - 不新增或修改 runtime/API/tasks/db/core 代码。
  - 不修改 DockerHost adapter、发布、回滚、envctl 或 deployment 文件。
  - 不把 dashboard/rules 直接安装到生产 Grafana、Prometheus 或 Alertmanager。
  - 不新增 Alertmanager route、paging receiver 或生产 MCP token。
  - 不写入真实 provider key、Grafana token、DockerHost token、用户 token、原始 prompt、生产日志原文。
  - 不改变现有 auth、tenant、quota、RAG 或 provider 行为。

## Product Semantics

- External requirements:
  - 内部运维和 Agent 必须能在 incident、release smoke、容量验证和 provider 异常时按同一 runbook 查询生产日志、观察核心面板、判断告警优先级并执行排障。
  - 观测体系必须覆盖 API、streaming、provider、Celery worker、event bus、Redis/Postgres readiness、reaper 和 RAG/pgvector 依赖。
  - Grafana MCP 查询必须先满足授权、source/env/service/time/limit 边界,默认读取 redacted log content。
  - 告警规则必须给出可执行阈值、持续时间、严重级别和首要诊断路径。
  - 仓库必须提交 `ops/observability/chat_server_overview_dashboard.json` 和 `ops/observability/chat_server_alert_rules.yml`,用 Prometheus/metrics 口径表达请求量、错误率、TTFT、stream gap、provider 429/5xx、Celery、reaper、readiness。
  - `scripts/validate_observability_assets.py` 必须能离线校验资产结构和 secret hygiene,零外部依赖,退出码可用于后续 release gate。
  - 文档与资产必须通过离线 pytest 契约测试,防止退化成空文档、空资产或丢失关键 secret hygiene 约束。
- User/operator workflow:
  - Release operator 在部署前后读取 runbook,检查 `/readyz`、`/metrics`、核心面板和 bounded log query。
  - Observability owner 在生产安装前先运行 `.venv/bin/python scripts/validate_observability_assets.py`,再把 dashboard JSON 和 alert rules YAML 导入对应平台。
  - On-call operator 收到告警后按严重级别进入 runbook 对应排障路径,优先确认 readiness、错误率、TTFT、stream token gap、provider 429/5xx、Celery backlog、reaper 状态。
  - Agent 代查日志时必须先声明 source/service/env/time window/limit,通过授权 Grafana MCP endpoint 查询,并只引用 `line_redacted` 或聚合结论。
- State model:
  - Observability state 分为 `healthy`、`degraded`、`incident`、`unknown`。
  - `healthy`: `/readyz` ready,错误率/TTFT/token gap/provider/Celery/reaper 均低于告警阈值。
  - `degraded`: 某个 dependency 或 provider 指标异常,但 Chat accepted/run terminal state 仍可收敛。
  - `incident`: 用户可见错误率、provider fail-closed、streaming 长时间无 token、队列积压或 reaper 无法收敛 stale run。
  - `unknown`: 指标缺失、日志查询未授权、dashboard stale 或无法确认数据窗口。
- Ownership and identity rules:
  - 生产日志和 dashboards 由授权 operator/on-call 查询。
  - Agent 可以辅助查询和总结,但不得请求、打印、粘贴或持久化 token 值。
  - 用户身份、Authorization header、provider API key、Grafana token、DockerHost token、database URL、Redis URL、原始 prompt 和模型原始响应均视为敏感数据。
- Permissions/authentication:
  - Grafana MCP `/v1/*` 请求必须使用匹配 source 的 Bearer token,token 只从本地私有 env 文件或安全 secret 注入环境读取。
  - Runbook 可记录 env var 名称和查询形状,不得记录真实 token 值。
  - `/metrics` 与 `/readyz` 的生产访问策略由部署平台控制;本切片只描述观测合同。
- Empty, error, retry, timeout, duplicate, and partial-failure behavior:
  - 若 metrics 某项缺失,operator 必须退回 bounded logs 与 `/readyz` 交叉验证,不得把缺失指标当作健康。
  - 若 Grafana MCP 查询失败,先缩小 source/service/env/time/limit 并确认授权;不得扩大到 broad LogQL 或无界 tail。
  - 若 `line_redacted` 缺少原文细节,只能基于 redacted 内容、labels、status code、run_id/trace_id 等非敏感字段判断。
  - 若 alert flaps,应先检查部署时间、traffic shape、provider quota 与 dashboard scrape lag。
- Compatibility and migration expectations:
  - 本规格不改变任何 API、event、DB schema、Redis key、Celery task 或 provider contract。
  - 新 runbook 与契约测试是 additive,不影响现有 production readiness runbook。

## API / Interface Contract

- Routes, commands, events, jobs, or UI surfaces:
  - `docs/OBSERVABILITY_AND_ALERTING_RUNBOOK.md` 是内部运维/Agent 观测告警入口。
  - `tests/test_observability_alerting_runbook_contract.py` 是离线文档契约测试。
  - `ops/observability/chat_server_overview_dashboard.json` 是可提交 Grafana dashboard 资产。
  - `ops/observability/chat_server_alert_rules.yml` 是可提交 Prometheus alert rules 资产。
  - `scripts/validate_observability_assets.py` 是零外部依赖离线资产校验 CLI。
  - `tests/test_observability_assets.py` 是 dashboard/rules/validator pytest 契约测试。
  - Grafana MCP 推荐接口为 bounded `POST /v1/logs`,请求必须包含 `source`、`service`、`env`、`time`、`limit`。
  - `GET /v1/logs/tail` 仅允许短时 live investigation;默认禁止无界 tail 和 broad LogQL。
  - `/readyz` 与 `/metrics` 是 runbook 中的本服务观测面,不在本切片中修改。
- Request fields and validation:
  - `POST /v1/logs` runbook 示例必须使用占位或环境变量,不得内联 token。
  - `source` 只能使用已授权生产源,当前支持 `btcfun` 与 `merlinchain`。
  - `service` 必须指向具体 Chat Server API、worker、reaper 或相关 job label。
  - `env` 必须为明确环境值,例如 `prod`、`test` 或部署平台定义值。
  - `time` 必须为有限窗口,默认从 `now-15m` 到 `now`,incident 扩展也应说明原因。
  - `limit` 必须为有限整数,默认不超过 `200`。
- Response/envelope fields and types:
  - Runbook 必须强调 Grafana MCP 返回的日志正文以 `line_redacted` 为准。
  - Runbook 不得要求访问 raw unredacted production logs。
  - Runbook 的诊断输出应记录 query window、source、service、env、limit、聚合结论、next action,不得记录 token 或 secret 值。
- Status/error codes:
  - `/readyz` 非 200 应视为 readiness incident 或 deployment gate blocker。
  - `/metrics` 404/空输出应视为 observability gap,需要回退日志和 deployment config 排查。
  - Grafana MCP 401/403 表示授权问题,不得通过打印 token 或复制 token 到 prompt 解决。
- Pagination/sorting/filtering:
  - 日志查询优先按 `time` window、`service`、`env`、`level/status/error`、`trace_id/run_id` 过滤。
  - 多页/多批查询必须逐步缩小或移动时间窗口,不得一次拉取无界历史。
- Backward compatibility:
  - 现有 `docs/PRODUCTION_READINESS_RUNBOOK.md` 保持生产部署 readiness/runbook 入口。
  - 新 runbook 只补充生产观测与告警,不取代 release gate。

## Data / Schema / Projection Impact

- Tables, indexes, migrations, backfills:
  - 无 DB schema 变更。
- Read models, projections, snapshots, caches:
  - 无 Redis/Postgres projection 变更。
- Rebuild or cleanup operators:
  - 不新增 rebuild/cleanup operator。
- Historical data behavior:
  - 历史日志只通过 bounded query 查询;不得导出未脱敏日志。
- Performance-sensitive queries or write paths:
  - 本切片不在 hot path 增加指标采样或网络调用。
  - Runbook 要求日志查询限时限量,避免生产观测查询本身放大故障。

## Architecture

- Modules/files expected to change:
  - `docs/specifications/2026-06-23-chat-server-observability-alerting-specification.md`
  - `docs/implementation-plans/2026-06-23-chat-server-observability-alerting-implementation-plan.md`
  - `docs/OBSERVABILITY_AND_ALERTING_RUNBOOK.md`
  - `tests/test_observability_alerting_runbook_contract.py`
  - `ops/observability/chat_server_overview_dashboard.json`
  - `ops/observability/chat_server_alert_rules.yml`
  - `scripts/validate_observability_assets.py`
  - `tests/test_observability_assets.py`
- Data flow:
  - Chat Server emits readiness and metrics through existing runtime surfaces.
  - Production logs are queried through authorized Grafana MCP using bounded filters.
  - Committed observability assets are validated offline, then imported by the production observability owner through the platform-specific Grafana/Prometheus workflow.
  - Operator correlates dashboard panels, `/readyz`, `/metrics`, redacted logs, run_id/trace_id and deployment event timeline.
  - Alert triage writes only sanitized evidence into incident notes or handoff summaries.
- Transaction/concurrency boundaries:
  - 不涉及 runtime transaction 或 concurrency 变更。
  - 观测查询不得触发 write action、deployment rollback 或 provider config change;这些动作需要单独明确确认。
- Runtime metrics:
  - Dashboard asset: `ops/observability/chat_server_overview_dashboard.json`。
  - Alert rules asset: `ops/observability/chat_server_alert_rules.yml`。
  - Validator command: `.venv/bin/python scripts/validate_observability_assets.py`。
  - 请求量: `chat_requests_total` 或 HTTP request counter,按 route/status/runtime_mode/provider 分组。
  - 错误率: HTTP 5xx/4xx、chat acceptance failure、stream error event、run failed terminal state。
  - TTFT: `chat_ttft_seconds` p50/p95/p99,按 runtime_mode/provider/model 分组。
  - 流式 token gap: `chat_stream_token_gap_seconds` token delta 间隔 p95/p99、last-token age、`chat_stream_stalls_total` stream stall/error event。
  - Provider 429/5xx: `provider_errors_total`、provider backoff、rate-limit decisions、usage missing。
  - Celery 队列: `celery_queue_depth`、`celery_oldest_queued_age_seconds`、worker active/reserved/retry/failures。
  - Reaper: `reaper_runs_total`、`reaper_requeued_total`、`reaper_failed_total`、last successful scan age、stale runs inspected。
  - Dependencies: `/readyz.checks.db`、`redis`、`event_bus`、`provider_secret`、`provider_limiter`、`reaper`,以及部署/采集层映射出的 `chat_readyz_check{check=...}`。
- Log queries:
  - Prefer bounded `POST /v1/logs` with explicit source/service/env/time/limit.
  - Use `line_redacted`, labels, timestamps, trace_id/run_id and status fields.
  - Avoid broad LogQL such as `{job=~".+"}` except tiny smoke tests with small limit and explicit reason.
  - Use `GET /v1/logs/tail` only for short live investigations and stop it after the observation window.
- Alert thresholds:
  - P0: suspected secret/token leak in logs, readiness hard down for all replicas, sustained user-visible 5xx > 5% for 5m, provider fail-closed across all traffic, or stream stalls affecting most realtime runs.
  - P1: `/readyz` not ready for 2m, API 5xx > 2% for 5m, TTFT p95 > 10s for 10m, stream token gap p95 > 15s for 5m, Celery oldest queued age > 300s, reaper no successful scan for 2 intervals, provider 5xx > 2% for 10m, provider 429 spike causing admitted runs to fail.
  - P2: TTFT p95 > 5s for 10m, provider 429 > 5/min for 10m, Celery queue depth > 100 for 10m, reaper requeue/failed count rises above baseline, metrics scrape stale for 5m.
  - Informational: deploy started/finished, provider quota config changed, mock provider enabled in non-prod smoke, RAG ingestion backlog observed without user-facing failures.
- Diagnostic flow:
  - Start with symptom scope: affected env, source, service, route, provider, runtime_mode, time window.
  - Check `/readyz` and dashboard freshness before deep logs.
  - Correlate request volume/error rate with deployment timeline and provider error panels.
  - Use bounded logs around first error spike and include only redacted snippets or aggregates.
  - Pick the matching runbook path: readiness, API errors, TTFT/token gap, provider 429/5xx, Celery backlog, reaper stale runs, RAG dependency, suspected secret leak.
  - Escalate to rollback or config change only after evidence identifies runtime, provider, queue, dependency, or deployment as likely cause.
- Secret redaction boundary:
  - Never print, paste, commit, attach, or summarize actual values for Grafana token, DockerHost token, provider API key, DB URL password, Redis password, Authorization header, X-API-Key, session cookie, private key, raw prompt containing user private data, or unredacted production log line.
  - Allowed in docs: env var names, source names, service names, metric names, route names, status words, redacted log field names, placeholder text such as `<service>`.
  - If a secret appears in tool output, stop quoting it, report that sensitive output was observed, and continue only with sanitized metadata.
- Rollback strategy:
  - Documentation-only rollback is deleting or reverting this spec/plan/runbook/test.
  - Operational rollback procedures remain in `docs/PRODUCTION_READINESS_RUNBOOK.md` and DockerHost owner workflow; this slice does not alter them.

## Harness Classification

- Expected gate(s):
  - `HARNESS-SPEC-FIRST-FEATURE`
  - Focused pytest for document contract.
  - Focused pytest for observability assets and validator.
  - Harness spec/workflow checks if release gate is run.
- Performance-sensitive class:
  - Low implementation risk because no runtime code changes.
  - High operational relevance because alert thresholds and log query bounds affect incident handling.
- Whether harness mapping must be extended:
  - No new workflow class required.
- Required performance evidence:
  - No new runtime performance evidence required for this docs/test slice.
  - Runbook must define runtime performance panels and alert thresholds for future production validation.
- Focused verification commands:
  - `.venv/bin/python -m pytest tests/test_observability_alerting_runbook_contract.py -q`
  - `.venv/bin/python -m pytest tests/test_observability_alerting_runbook_contract.py tests/test_observability_assets.py -q`
  - `.venv/bin/python scripts/validate_observability_assets.py`
  - `scripts/check_spec_contract.sh`
  - `scripts/check_harness_workflows.sh`
- Prerelease-grade verification commands:
  - `make verify-release` (includes the `observability_assets` validator gate)

## Acceptance Criteria

- Functional:
  - Spec declares `SPEC-CHAT-OBSERVABILITY-ALERTING-001` and `Workflow Class: HARNESS-SPEC-FIRST-FEATURE`。
  - Implementation plan references this spec ID and lists file-level steps, tests, release/rollback risks。
  - Runbook is Chinese, operator-facing, and includes Grafana MCP prerequisites, bounded `/v1/logs` query guidance, dashboard panels, alert rules, diagnostic paths, and secret redaction boundaries。
  - Dashboard asset `ops/observability/chat_server_overview_dashboard.json` contains Prometheus panels for request rate, API error rate, TTFT, stream token gap, provider 429/5xx, Celery, reaper and readiness。
  - Alert rules asset `ops/observability/chat_server_alert_rules.yml` contains Prometheus rules with severity, threshold expression, duration and runbook annotations。
  - Validator `scripts/validate_observability_assets.py` validates dashboard/rules structure and secret hygiene offline with only Python stdlib。
  - Contract tests read spec/plan/runbook/assets/validator and fail if critical sections or terms disappear。
- Edge cases:
  - Test must not require network, Grafana MCP, DockerHost, provider credentials, database, Redis, or environment variables。
  - Validator tests must use temporary fixtures for rejection cases and must not depend on Grafana or Prometheus binaries。
  - Runbook examples must use placeholders or env var names only。
  - Runbook must treat missing metrics/log authorization as `unknown`, not as healthy。
- Compatibility:
  - Existing production readiness docs remain intact。
  - Existing metrics/readiness tests remain untouched。
  - Parallel DockerHost worker files remain untouched。
- Operational:
  - Alerts include severity, threshold, duration, and first diagnostic path。
  - Secret hygiene covers token printing, raw logs, Authorization headers, provider keys and private credentials。
  - Bounded log query guidance includes source, service, env, time, limit and redacted output usage。
- Evidence artifacts:
  - This specification。
  - Implementation plan。
  - Observability and alerting runbook。
  - Grafana dashboard JSON。
  - Prometheus alert rules YAML。
  - Offline observability asset validator。
  - Focused pytest output。

## Review Notes

- Open questions:
  - Final production dashboard import, Prometheus rule loading, Alertmanager routing and on-call ownership are external to this repository。
  - Exact service/job labels should be updated when production deployment naming is finalized。
  - Final threshold tuning needs real traffic baseline and provider quota data。
- Accepted assumptions:
  - Committed dashboard/rules assets are acceptable repository artifacts before production installation and threshold tuning。
  - Grafana MCP redaction is the default evidence boundary; raw logs are not required for this runbook。
  - `SPEC-PROD-READINESS-001` remains authoritative for deploy/readiness/rollback mechanics。
- Rejected alternatives:
  - Rejected writing real secret values, example tokens, or unredacted log snippets。
  - Rejected editing DockerHost files in this slice because another worker owns deployment/rollback。
  - Rejected adding runtime metrics code without a separate implementation scope and owner approval。
- Reviewer findings and resolution:
  - Pending focused document contract verification。
