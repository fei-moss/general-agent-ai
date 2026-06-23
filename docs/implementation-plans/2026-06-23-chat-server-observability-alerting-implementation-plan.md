# 2026-06-23 Chat Server 生产观测与告警体系完善 Implementation Plan

## Plan Header

- Specification: `docs/specifications/2026-06-23-chat-server-observability-alerting-specification.md`
- Spec ID: `SPEC-CHAT-OBSERVABILITY-ALERTING-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Target branch/baseline: `codex/zai-glm52-dockerhost`
- Scope summary: 新增生产观测与告警体系的中文 spec、中文 implementation plan、中文 operator/Agent runbook、离线 pytest 文档契约测试。该切片只写入 4 个新文件,不修改 runtime/API/DockerHost 发布回滚文件。
- Out of scope:
  - 修改 `app/` runtime、API、metrics、health、tasks、db 或 provider 行为。
  - 修改 DockerHost compose/template/env/deploy/rollback 文件。
  - 创建真实 Grafana dashboard、Prometheus alert rule 或 Alertmanager route。
  - 查询生产日志、打印 token、写入真实 secret。
  - 执行 deployment、rollback、branch-space 或 envctl 操作。

## Change Steps

### 1. Specification

- Files/modules:
  - `docs/specifications/2026-06-23-chat-server-observability-alerting-specification.md`
- Behavior change:
  - 建立 `SPEC-CHAT-OBSERVABILITY-ALERTING-001` 作为生产观测与告警切片的稳定合同。
  - 声明 `Workflow Class: HARNESS-SPEC-FIRST-FEATURE`。
  - 覆盖外部需求、运行时指标、日志查询、告警阈值、诊断流程、秘密脱敏边界。
- Data contract impact:
  - 无 API、DB、Redis、event 或 provider contract 变更。
- Tests to add/update:
  - 新增 pytest 文档契约测试断言 spec ID、Workflow Class、关键章节和关键术语存在。
- Verification command:
  - `.venv/bin/python -m pytest tests/test_observability_alerting_runbook_contract.py -q`
  - `scripts/check_spec_contract.sh`
- Rollback or compatibility note:
  - 文档新增可直接 revert;不影响现有 production readiness 行为。

### 2. Implementation Plan

- Files/modules:
  - `docs/implementation-plans/2026-06-23-chat-server-observability-alerting-implementation-plan.md`
- Behavior change:
  - 从 `SPEC-CHAT-OBSERVABILITY-ALERTING-001` 推导文件级实现计划。
  - 记录测试计划、发布/回滚风险、并行 worker 文件边界和完成标准。
- Data contract impact:
  - 无。
- Tests to add/update:
  - 文档契约测试断言 plan 引用 spec 路径、spec ID、Workflow Class、测试计划、发布风险、回滚风险和 4 个允许写入文件。
- Verification command:
  - `.venv/bin/python -m pytest tests/test_observability_alerting_runbook_contract.py -q`
  - `scripts/check_harness_workflows.sh`
- Rollback or compatibility note:
  - Plan 是 documentation artifact,可随 spec 一起 revert。

### 3. Observability And Alerting Runbook

- Files/modules:
  - `docs/OBSERVABILITY_AND_ALERTING_RUNBOOK.md`
- Behavior change:
  - 为内部运维/Agent 提供生产观测与告警入口。
  - 明确 Grafana MCP 查询前置条件、不要打印 token、推荐 bounded `POST /v1/logs` 查询、`line_redacted` 使用边界。
  - 定义核心面板:请求量、错误率、TTFT、流式 token gap、provider 429/5xx、Celery 队列、reaper、readiness/dependency。
  - 定义告警规则、严重级别、排障路径和 handoff evidence 形状。
- Data contract impact:
  - 无。
- Tests to add/update:
  - 文档契约测试断言 runbook 包含 Grafana MCP URL、`POST /v1/logs`、source/service/env/time/limit、`line_redacted`、核心面板词、告警阈值词、排障路径词和秘密脱敏边界。
  - 文档契约测试断言没有明显 secret literal,例如内联 Bearer token、provider API key 前缀或 private key marker。
- Verification command:
  - `.venv/bin/python -m pytest tests/test_observability_alerting_runbook_contract.py -q`
- Rollback or compatibility note:
  - Runbook 不替代 `docs/PRODUCTION_READINESS_RUNBOOK.md`;只是补充观测与告警操作。

### 4. Pytest Document Contract

- Files/modules:
  - `tests/test_observability_alerting_runbook_contract.py`
- Behavior change:
  - 添加离线 pytest,读取 spec/plan/runbook 并验证关键合同。
  - 测试不依赖网络、Grafana MCP、DockerHost、provider credentials、DB、Redis 或环境变量。
- Data contract impact:
  - 无。
- Tests to add/update:
  - `test_spec_declares_stable_contract_and_required_sections`
  - `test_plan_references_spec_and_delivery_scope`
  - `test_runbook_documents_grafana_mcp_bounded_log_queries`
  - `test_runbook_covers_panels_alerts_diagnostics_and_redaction`
  - `test_documents_are_non_empty_and_do_not_embed_obvious_secrets`
- Verification command:
  - `.venv/bin/python -m pytest tests/test_observability_alerting_runbook_contract.py -q`
- Rollback or compatibility note:
  - Test only protects new docs;不改变现有 test suite fixture 或 runtime state。

## Test Plan

- Focused:
  - `.venv/bin/python -m pytest tests/test_observability_alerting_runbook_contract.py -q`
- Harness/document checks:
  - `scripts/check_spec_contract.sh`
  - `scripts/check_harness_workflows.sh`
- Optional broader gate:
  - `make verify-release`
- Expected outcome:
  - Focused pytest passes without external services。
  - Spec contract recognizes new spec/plan and stable `SPEC-*` ID。
  - Harness workflow checker accepts `HARNESS-SPEC-FIRST-FEATURE` binding。

## Risk Controls

- Public contract risks:
  - None; no API or event shapes changed。
- Money/accounting/security risks:
  - Highest risk is accidentally documenting real credentials or unsafe log-query practices。
  - Mitigation: runbook uses env var names/placeholders only, pytest rejects obvious secret literals and requires token-printing prohibition。
- Migration/rebuild risks:
  - None; no schema, Redis, projection or data migration。
- Performance risks:
  - None in runtime; runbook recommends bounded log queries to avoid observability-induced load。
- Deployment/test-branch risks:
  - Parallel worker owns DockerHost deployment/rollback; this plan does not edit DockerHost files or invoke envctl。
  - `make verify-release` may include unrelated environment requirements; focused pytest is the required proof for this slice。
- Unrelated local changes to avoid:
  - Do not modify `docs/PRODUCTION_READINESS_RUNBOOK.md`。
  - Do not modify `app/core/metrics.py`。
  - Do not modify `app/api/routers/health.py`。
  - Do not modify `tests/test_production_readiness.py`。
  - Do not modify `dockerhost/` files。
  - Do not stage or revert files from the parallel worker。

## Release And Rollback Risk

- Release readiness:
  - The release artifact is documentation plus contract test; it can ship independently of runtime code。
  - Before merging, focused pytest and Harness doc checks should pass。
- Rollback:
  - Revert the four new files if the operational guidance is rejected。
  - No service restart, DB rollback, migration rollback or DockerHost release action is required for this slice。
- Residual risks:
  - Exact Grafana service/job labels may drift from production; runbook instructs operators to confirm labels before incident use。
  - Alert thresholds require real traffic baseline tuning after deployment。
  - Managed dashboard and alert rule installation remain external work。

## Completion Criteria

- `SPEC-CHAT-OBSERVABILITY-ALERTING-001` exists and includes required observability/alerting/security scope。
- Implementation plan references the spec ID and `HARNESS-SPEC-FIRST-FEATURE`。
- Runbook contains Grafana MCP bounded query guidance, dashboards, alerts, diagnostic paths, and secret redaction boundary。
- Pytest document contract exists and passes locally。
- No files outside the four allowed new files are modified。
- Final report lists modified files, test command, pass/fail status, and any residual risk。
