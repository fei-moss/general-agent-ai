# 2026-06-23 DockerHost Release Runbook Implementation Plan

## Plan Header

- Specification: `docs/specifications/2026-06-23-dockerhost-release-runbook-specification.md`
- Spec ID: `SPEC-DOCKERHOST-RELEASE-RUNBOOK-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Target branch/baseline: `codex/zai-glm52-dockerhost` at local baseline `da06fb5`
- Scope summary: 固化 DockerHost Git pull 发布、secret 注入、健康/流式/worker/reaper 验证、同环境 redeploy、回滚、清理与审计 runbook,并新增默认 dry-run 的辅助 CLI 与 pytest 契约守住关键门禁。
- Out of scope:
  - 修改 `dockerhost/compose.yaml`, `dockerhost/template.yaml`, `dockerhost/env.example`。
  - 修改 runtime/API/tasks/db/provider/streaming 行为。
  - 默认不执行真实 DockerHost 发布或访问网络;真实 `git`/`envctl`/`curl` 调用必须由 CLI 使用者显式传入 `--execute`。
  - 写入任何真实 secret、token、provider key 或本地凭据值。
  - 干预并行 worker 的生产观测告警文件。

## Change Steps

### 1. Specification

- Files/modules:
  - `docs/specifications/2026-06-23-dockerhost-release-runbook-specification.md`
- Behavior change:
  - 新增 `SPEC-DOCKERHOST-RELEASE-RUNBOOK-001` 作为本切片单一事实源。
  - 绑定 `Workflow Class: HARNESS-SPEC-FIRST-FEATURE`。
  - 明确 DockerHost 发布/回滚 runbook 与 CLI 的范围、非目标、验收标准、dry-run/execute 边界和 secret hygiene。
- Data contract impact:
  - None. 文档契约，不改变 API、DB 或 DockerHost adapter。
- Tests to add/update:
  - 后续 `tests/test_dockerhost_release_runbook_contract.py` 断言 spec ID、workflow class、CLI surface 和关键验收术语存在。
- Verification command:
  - `bash scripts/check_spec_contract.sh`
  - `bash scripts/check_harness_workflows.sh`
- Rollback or compatibility note:
  - 删除该新增 spec 即可回滚本步骤；不影响运行系统。

### 2. Implementation Plan

- Files/modules:
  - `docs/implementation-plans/2026-06-23-dockerhost-release-runbook-implementation-plan.md`
- Behavior change:
  - 将 `SPEC-DOCKERHOST-RELEASE-RUNBOOK-001` 拆成文件级交付步骤。
  - 固化测试计划、发布风险、回滚风险和未触碰文件边界。
- Data contract impact:
  - None.
- Tests to add/update:
  - 文档契约测试断言 plan 引用 spec ID、runbook、pytest 文件、verification commands、release/rollback 风险。
- Verification command:
  - `bash scripts/check_harness_workflows.sh`
- Rollback or compatibility note:
  - 删除该新增 plan 即可回滚本步骤；不影响运行系统。

### 3. DockerHost Release Runbook

- Files/modules:
  - `docs/DOCKERHOST_RELEASE_RUNBOOK.md`
- Behavior change:
  - 为内部运维/Agent 提供中文、可执行的 DockerHost 发布/回滚流程。
  - 包含:
    - `envctl` 前置条件与本地凭据安全边界。
    - 不打印 `ENVCTL_TOKEN` 或 provider key。
    - `envctl check-project` 与 `envctl validate-template` 发布前门禁。
    - Git pull deployment: `--git-url`, `--git-ref`, `--git-subdir dockerhost`。
    - `--secret-env` 与 `--secret-file` secret 注入方式。
    - `/healthz` 和 `/readyz` 验证。
    - `stream=false` 期望 `422 STREAM_FALSE_NOT_SUPPORTED`。
    - SSE 和 WebSocket smoke。
    - worker/reaper logs 验证。
    - 同环境 redeploy。
    - 回滚到上一 known-good SHA。
    - disposable env destroy 与审计清单。
- Data contract impact:
  - None.
- Tests to add/update:
  - 文档契约测试断言上述章节/术语存在。
  - 文档契约测试断言没有明显真实 secret 字面量或 `KEY=value` 示例。
- Verification command:
  - `.venv/bin/python -m pytest tests/test_dockerhost_release_runbook_contract.py -q`
- Rollback or compatibility note:
  - 该 runbook 是新增文档，不替换 `docs/PRODUCTION_READINESS_RUNBOOK.md`。

### 4. DockerHost Release CLI

- Files/modules:
  - `scripts/dockerhost_release.py`
- Behavior change:
  - 新增零外部 Python 依赖的 DockerHost release helper。
  - 默认 dry-run 输出有序 plan 和脱敏 audit JSON,不调用 `git`, `envctl` 或 `curl`。
  - 显式 `--execute` 后按顺序执行 git status/ref preflight、`envctl check-project`、`envctl validate-template`、`envctl up --git-url --git-ref --git-subdir dockerhost`、`/healthz`、`/readyz`、`stream=false` 422、accepted chat、SSE smoke、worker/reaper logs。
  - 支持 `deploy`, `redeploy`, `rollback --previous-sha`, `destroy`, `smoke`。
  - `--secret-env` 只接受 secret 名称并拒绝 inline `KEY=value`;`--secret-file KEY=PATH` 可传给真实 envctl 命令,但 stdout/audit 只保留 secret 名称和 redacted placeholder。
- Data contract impact:
  - None. 仅新增本地运维辅助脚本,不改变 API、DB、DockerHost adapter 或 release gate。
- Tests to add/update:
  - `tests/test_dockerhost_release_cli.py` 覆盖 dry-run plan、execute runner 参数、secret hygiene、rollback/destroy 计划。
- Verification command:
  - `.venv/bin/python -m pytest tests/test_dockerhost_release_cli.py -q`
- Rollback or compatibility note:
  - 删除该新增脚本和对应测试即可回滚本步骤；真实执行仍由 `--execute` 显式控制。

### 5. DockerHost Release CLI Contract

- Files/modules:
  - `tests/test_dockerhost_release_cli.py`
- Behavior change:
  - 新增 pytest 覆盖 CLI 行为,使用注入 runner 和本地 stdout/stderr 捕获。
  - 测试不访问 DockerHost、网络、真实 `envctl`、真实 `curl`、secret 文件内容或 provider 服务。
  - 测试确保 dry-run 不执行外部命令、execute 模式向 runner 传入真实 secret-file 路径但 audit/stdout 脱敏、rollback 使用上一 SHA、destroy 只规划 unexpose/down。
- Data contract impact:
  - None.
- Tests to add/update:
  - `test_deploy_dry_run_plans_ordered_release_steps_without_execution`
  - `test_execute_mode_runs_commands_with_real_secret_file_path_but_redacted_audit`
  - `test_secret_arguments_reject_inline_values_and_audit_only_secret_names`
  - `test_execute_queries_run_status_when_sse_lacks_terminal_event`
  - `test_rollback_and_destroy_default_to_safe_dry_run_plans`
- Verification command:
  - `.venv/bin/python -m pytest tests/test_dockerhost_release_cli.py -q`
- Rollback or compatibility note:
  - 删除该新增测试即回滚 CLI contract；不影响 runtime。

### 6. Executable Documentation Contract

- Files/modules:
  - `tests/test_dockerhost_release_runbook_contract.py`
- Behavior change:
  - 新增/更新 pytest 文档契约测试,只读取本切片 docs 和检查 CLI 术语。
  - 不访问 DockerHost、网络、Docker daemon、provider 服务或真实凭据。
  - 测试失败时指出缺失术语，方便未来编辑者恢复发布门禁。
- Data contract impact:
  - None.
- Tests to add/update:
  - `test_spec_and_plan_bind_to_stable_spec_id_and_workflow`
  - `test_runbook_contains_release_and_rollback_gates`
  - `test_runbook_contains_cli_dry_run_and_execute_boundaries`
  - `test_runbook_preserves_secret_hygiene_contract`
- Verification command:
  - `.venv/bin/python -m pytest tests/test_dockerhost_release_runbook_contract.py -q`
- Rollback or compatibility note:
  - 删除该新增测试即回滚测试 gate；不影响 runtime。

## Testing Plan

- Focused:
  - `.venv/bin/python -m pytest tests/test_dockerhost_release_cli.py -q`
  - `.venv/bin/python -m pytest tests/test_dockerhost_release_runbook_contract.py -q`
  - `.venv/bin/python -m pytest tests/test_dockerhost_release_cli.py tests/test_dockerhost_release_runbook_contract.py -q`
- Harness/spec:
  - `bash scripts/check_spec_contract.sh`
  - `bash scripts/check_harness_workflows.sh`
- Prerelease:
  - `make verify-release`
- Expected constraints:
  - 所有测试在本地文件系统上运行。
  - 不需要 DockerHost token、provider key、网络、Docker daemon、真实 `envctl`、真实 `curl` 或 live environment。

## Release And Rollback Risks

- Release risks:
  - Runbook 如果遗漏 `envctl check-project` 或 `envctl validate-template`,Operator 可能把不可解析 adapter 推到远端环境。
  - Runbook 如果遗漏 `stream=false` 422,可能错过 `SPEC-ASYNC-CHAT-ONLY-001` 回归。
  - Runbook 如果遗漏 worker/reaper logs,可能在 API ready 但后台执行不可用时误判发布完成。
  - Runbook 如果写入真实 secret 或 `KEY=value` 示例,可能被提交、复制到 PR 或进入审计证据。
  - CLI 如果默认执行真实命令,可能在 plan 阶段误触发布、网络 smoke 或 destroy。
  - CLI 如果把 `--secret-file KEY=PATH` 的 PATH 或命令输出原样写入 audit,可能泄露本机私有路径或 secret 内容。
- Rollback risks:
  - 回滚到上一 SHA 不能自动解决未来 schema migration 兼容问题;如 release 引入 DB migration,Operator 必须先检查 backward/forward compatibility。
  - 同环境 rollback/redeploy 可能需要再次传入一次性 `--secret-env`/`--secret-file`。
  - Disposable cleanup 不适用于承载长期数据的环境;`envctl down` 前必须确认数据可以销毁或已备份。
- Risk controls:
  - `SPEC-DOCKERHOST-RELEASE-RUNBOOK-001` 明确验收条件。
  - Pytest 文档契约锁定关键门禁和 secret hygiene 术语。
  - CLI pytest 锁定 dry-run 默认、安全执行边界、secret 脱敏、rollback/destroy 行为。
  - Final verification 同时跑 focused pytest 与 Harness spec/workflow checks。

## Completion Criteria

- `SPEC-DOCKERHOST-RELEASE-RUNBOOK-001` spec 和本 implementation plan 均声明 `Workflow Class: HARNESS-SPEC-FIRST-FEATURE`。
- `scripts/dockerhost_release.py` 支持 `deploy`, `redeploy`, `rollback`, `destroy`, `smoke`,默认 dry-run,仅在 `--execute` 时调用外部命令。
- `docs/DOCKERHOST_RELEASE_RUNBOOK.md` 覆盖 Git pull deployment、secret 注入、健康/ready、流式 chat smoke、worker/reaper、redeploy、rollback、cleanup、audit。
- `tests/test_dockerhost_release_runbook_contract.py` 只做本地文档契约检查。
- `tests/test_dockerhost_release_cli.py` 只做本地 CLI plan/runner 契约检查。
- Focused pytest 通过。
- Spec contract 与 Harness workflow check 通过。
- 如运行 `make verify-release`,结果在最终汇报中明确说明。
