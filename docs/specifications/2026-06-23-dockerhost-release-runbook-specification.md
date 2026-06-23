# 2026-06-23 DockerHost Release Runbook Specification

## Context

- Spec ID: `SPEC-DOCKERHOST-RELEASE-RUNBOOK-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- PRD/source request: 将 DockerHost Git pull 发布、验证、同环境 redeploy、回滚、清理与审计流程固化为内部运维/Agent 可执行 runbook,并补上默认 dry-run 的辅助 CLI 与 pytest 契约防止关键门禁缺失。
- Target baseline: branch `codex/zai-glm52-dockerhost`, local baseline `da06fb5`.
- Current behavior:
  - `dockerhost/compose.yaml` 已定义 `api`, `worker`, `reaper`, `db`, `cache` 服务,使用 Compose service name 互联,并通过 healthcheck 覆盖 API `/healthz`, worker Celery ping, reaper bounded dry-run, Postgres 和 Redis。
  - `dockerhost/template.yaml` 已声明 `api`, `db`, `cache` 暴露形态与 `postgres-data` managed volume。
  - `dockerhost/env.example` 已记录 mock/provider/RAG/worker/reaper 默认配置,并提示 provider secret 通过 `envctl --secret-env` 注入。
  - `docs/PRODUCTION_READINESS_RUNBOOK.md` 已覆盖生产就绪视角,但本切片需要一份专门面向 DockerHost 发布和回滚的操作手册。
- Problem: DockerHost 发布涉及本地凭据、Git ref、平台校验、provider secret 注入、健康检查、流式 chat smoke、worker/reaper 诊断、回滚和环境销毁。如果这些步骤只存在于聊天记录、分散文档或手工命令中,后续 Agent/运维容易漏过发布前门禁、泄露 secret、用错误 ref 发布,或回滚后没有验证。
- Non-goals:
  - 不修改 runtime/API/task/db/compose/template/env 行为。
  - 默认不执行真实 DockerHost 发布、网络 smoke 或生产观测查询;真实 `envctl`/`curl` 调用必须由 CLI 使用者显式传入 `--execute`。
  - 不写入真实 `ENVCTL_TOKEN`, provider API key, bearer token, private key, secret file 内容或本地凭据值。
  - 不改并行 worker 负责的生产观测告警文件。

## Product Semantics

- User/operator workflow:
  - Operator 在本地私有环境中加载 `envctl` 凭据,但不得打印、复制或提交 `ENVCTL_TOKEN`。
  - Operator 选择目标环境名、Git URL、Git ref 或 SHA,确认该 ref 已推送且可被 DockerHost Git pull deployment 拉取。
  - Operator 在每次部署前执行 `envctl check-project` 与 `envctl validate-template`,确认 `dockerhost/` adapter 可被平台解析。
  - Operator 使用 `--secret-env` 或 `--secret-file` 传入 provider secret 名称或私有文件路径,不得使用会进入 shell history/log 的明文 secret 参数。
  - Operator 可先运行 `.venv/bin/python scripts/dockerhost_release.py <action> ...` 生成 dry-run plan 和脱敏 audit JSON;只有显式 `--execute` 才允许 CLI 调用 `git`, `envctl` 或 `curl`。
  - Operator 对同一环境执行初次 deploy 或 redeploy 后,必须验证 `envctl status`, `/healthz`, `/readyz`, `stream=false` 422, SSE/WebSocket chat smoke, worker logs, reaper logs。
  - Operator 回滚时必须选择上一 known-good SHA,在同一环境 redeploy 该 SHA,并重复健康检查、流式 smoke、worker/reaper 验证。
  - Operator 仅在 disposable environment 中执行 `envctl down`;如环境承载长期或生产数据,必须先确认备份/迁移策略。
- State model:
  - 发布状态以环境名、Git URL、Git ref、解析后的 commit SHA、部署时间、验证结果、回滚目标和清理结果记录。
  - Secret 只以 secret 名称或 secret file 路径类别进入审计记录,不得记录 secret 值。
  - CLI audit JSON 记录 action、dry-run/execute 状态、环境名、Git ref、secret 名称、步骤顺序、脱敏命令、执行状态与脱敏 stdout/stderr 摘要。
  - Smoke 证据以状态码、run id/conversation id、SSE/WebSocket 是否接收 terminal event、worker/reaper log 摘要记录。
- Ownership and identity rules:
  - Runbook 面向内部运维和授权 Agent。
  - 业务 smoke 使用专用 smoke identity,不得复用真实用户 token 或 provider key 作为请求 Authorization。
- Permissions/authentication:
  - DockerHost API 调用需要本地 `envctl` 凭据。
  - Chat smoke 仍遵循现有 API header-derived identity 规则。
  - 本规格不新增正式 auth/tenant/API-key 体系。
- Empty, error, retry, timeout, duplicate, and partial-failure behavior:
  - `envctl check-project` 或 `envctl validate-template` 失败时,不得继续部署。
  - `/readyz` 非 200、provider secret missing、Redis/DB/event bus/provider limiter 不 ready 时,不得切流或宣称发布完成。
  - `stream=false` 未返回 422 或错误码不是 `STREAM_FALSE_NOT_SUPPORTED` 时,视为 async-only chat contract 回归。
  - SSE 或 WebSocket smoke 没有 terminal event 时,必须查询 `/runs/{agent_run_id}` 并保留失败/超时证据。
  - Worker/reaper logs 出现启动失败、secret 泄露、reaper dry-run 失败或 Celery ping 失败时,必须先修复或回滚。
  - 同环境 redeploy 必须重新传入一次性 secret 参数,除非平台明确持久化该 secret 配置并已被验证。
- Compatibility and migration expectations:
  - 本规格新增文档、CLI 脚本和本地 pytest 契约,不改变现有 API 或 DockerHost adapter。
  - 现有 `docs/PRODUCTION_READINESS_RUNBOOK.md` 保持生产就绪总览职责;新增 runbook 专注发布/回滚步骤。

## API / Interface Contract

- Routes, commands, events, jobs, or UI surfaces:
  - Document surface: `docs/DOCKERHOST_RELEASE_RUNBOOK.md`。
  - Spec surface: `docs/specifications/2026-06-23-dockerhost-release-runbook-specification.md`。
  - Plan surface: `docs/implementation-plans/2026-06-23-dockerhost-release-runbook-implementation-plan.md`。
  - CLI surface: `scripts/dockerhost_release.py`。
  - Executable contracts:
    - `tests/test_dockerhost_release_runbook_contract.py`
    - `tests/test_dockerhost_release_cli.py`
  - CLI actions:
    - `deploy`: plan or execute Git pull deployment and post-deploy smoke/log checks.
    - `redeploy`: same environment deployment to a new branch or SHA.
    - `rollback`: same environment deployment to `--previous-sha`, followed by smoke/log checks.
    - `destroy`: disposable cleanup plan for DB/cache unexpose and `envctl down`.
    - `smoke`: health/readiness/async chat/log validation without changing Git ref.
  - CLI safety contract:
    - Dry-run is the default and must not invoke `git`, `envctl` or `curl`.
    - `--execute` is required before any command is run.
    - `--audit-json` writes the same redacted audit JSON that is printed to stdout.
    - `--secret-env` accepts secret names only and rejects inline `KEY=value`.
    - `--secret-file` accepts `KEY=PATH` for envctl execution, but audit/stdout may record only the secret name and a redacted file placeholder.
  - Required commands/terms in the runbook:
    - `envctl version`
    - `envctl check-project --dir /Users/chris/AiProject/general-agent-ai`
    - `envctl validate-template --dir /Users/chris/AiProject/general-agent-ai/dockerhost`
    - `envctl up --git-url ... --git-ref ... --git-subdir dockerhost`
    - `.venv/bin/python scripts/dockerhost_release.py deploy`
    - `.venv/bin/python scripts/dockerhost_release.py redeploy`
    - `.venv/bin/python scripts/dockerhost_release.py rollback --previous-sha`
    - `.venv/bin/python scripts/dockerhost_release.py destroy`
    - `.venv/bin/python scripts/dockerhost_release.py smoke`
    - `--execute`
    - `--audit-json`
    - `--secret-env`
    - `--secret-file`
    - `/healthz`
    - `/readyz`
    - `stream=false` returns `422 STREAM_FALSE_NOT_SUPPORTED`
    - SSE smoke and WebSocket smoke
    - worker and reaper log checks
    - rollback to previous SHA
    - `envctl down` for disposable environments
- Request fields and validation:
  - No new application request fields.
  - Runbook smoke must continue using existing `POST /chat` shape with `message`, optional `metadata`, and `stream=true` or omitted.
  - Runbook must explicitly test unsupported `stream=false` with expected `422` before any successful smoke is considered complete.
- Response/envelope fields and types:
  - `/healthz` must return successful process liveness before deeper checks.
  - `/readyz` must return ready only when DB, Redis, event bus, provider secret and provider limiter are ready; the runbook must instruct operators not to print secret values.
  - `POST /chat` accepted smoke should capture `agent_run_id`, `conversation_id`, `stream_url` and `ws_url` when present.
- Status/error codes:
  - `stream=false` smoke expects HTTP `422` and `STREAM_FALSE_NOT_SUPPORTED`。
  - `/readyz` non-200 blocks release completion.
  - Failed SSE/WebSocket smoke blocks release completion unless a documented rollback is executed.
- Backward compatibility:
  - The docs must not describe synchronous Chat response waiting as supported.
  - The docs may reference both SSE and WebSocket because both are already part of async chat recovery surfaces.

## Data / Schema / Projection Impact

- Tables, indexes, migrations, backfills:
  - None.
- Read models, projections, snapshots, caches:
  - None.
- Rebuild or cleanup operators:
  - Runbook documents `envctl down` for disposable environment cleanup.
  - Runbook documents `envctl unexpose` for temporary DB/cache exposure cleanup when applicable.
- Historical data behavior:
  - Rollback to an older SHA may reuse the same Postgres volume. The runbook must require operators to check migration/data compatibility before rollback if a future release changes schema.
- Performance-sensitive queries or write paths:
  - None in code. Live smoke/load commands remain operator actions and are bounded.

## Architecture

- Modules/files expected to change:
  - `docs/specifications/2026-06-23-dockerhost-release-runbook-specification.md`
  - `docs/implementation-plans/2026-06-23-dockerhost-release-runbook-implementation-plan.md`
  - `docs/DOCKERHOST_RELEASE_RUNBOOK.md`
  - `tests/test_dockerhost_release_runbook_contract.py`
  - `scripts/dockerhost_release.py`
  - `tests/test_dockerhost_release_cli.py`
- Data flow:
  - Human/Agent reads spec and plan.
  - Operator uses the CLI in default dry-run mode to inspect ordered git/envctl/curl steps and redacted audit output.
  - With explicit `--execute`, the CLI runs git preflight, DockerHost adapter validation, Git pull deployment, health/readiness checks, async chat contract smoke, SSE smoke, worker/reaper log checks, and records redacted audit evidence.
  - DockerHost pulls the requested Git ref from the pushed repository and starts the `dockerhost/` compose stack.
  - Operator redeploys another ref for forward fix or previous SHA for rollback, then repeats verification through the CLI or the manual runbook.
- Transaction/concurrency boundaries:
  - No code transaction changes.
  - Runbook must warn that parallel workers may edit other files and that this slice only owns the scoped docs, CLI script, and tests.
- Observability/logging/metrics:
  - Runbook uses `envctl status` and bounded `envctl logs --tail` for worker/reaper validation.
  - Runbook may mention `/metrics` as optional supporting evidence, but release completion in this slice is based on health/readiness, stream smoke and worker/reaper checks.
- Rollback strategy:
  - Capture the current good SHA before deployment.
  - Deploy candidate Git ref.
  - On release-blocking failure, redeploy previous known-good SHA to the same environment using the same secret injection mechanism.
  - Re-run `/healthz`, `/readyz`, `stream=false` 422, SSE/WebSocket smoke, worker logs and reaper logs before declaring rollback complete.

## Harness Classification

- Expected gate(s):
  - `HARNESS-SPEC-FIRST-FEATURE`
  - Spec first, implementation plan second, CLI/runbook and executable contracts third.
- Performance-sensitive class:
  - Indirectly yes. The runbook verifies streaming, worker and reaper behavior for production-like deployments, but this slice itself does not change hot paths.
- Whether harness mapping must be extended:
  - No. `HARNESS-SPEC-FIRST-FEATURE` already covers config/release-sensitive operational behavior.
- Required performance evidence:
  - No new benchmark artifact for this release-automation slice.
  - Runbook must instruct operators to keep live smoke bounded and record status/run evidence.
- Focused verification commands:
  - `.venv/bin/python -m pytest tests/test_dockerhost_release_cli.py -q`
  - `.venv/bin/python -m pytest tests/test_dockerhost_release_runbook_contract.py -q`
  - `bash scripts/check_spec_contract.sh`
  - `bash scripts/check_harness_workflows.sh`
- Prerelease-grade verification commands:
  - `make verify-release`
  - Live DockerHost deployment remains an operator action; this change provides a dry-run-first helper and requires `--execute` for real commands.

## Acceptance Criteria

- Functional:
  - Specification declares `SPEC-DOCKERHOST-RELEASE-RUNBOOK-001` and `Workflow Class: HARNESS-SPEC-FIRST-FEATURE`。
  - Implementation plan references this spec ID and maps each target file to a verification step。
  - `scripts/dockerhost_release.py` uses only the Python standard library and supports `deploy`, `redeploy`, `rollback`, `destroy`, and `smoke`。
  - CLI defaults to dry-run plan/audit mode; true `git`/`envctl`/`curl` execution requires `--execute`。
  - CLI passes `--secret-env` and `--secret-file` names to `envctl`, rejects inline `--secret-env KEY=value`, and never prints or audits secret values or secret file contents。
  - CLI plan/execute order includes git status/ref preflight, `envctl check-project`, `envctl validate-template`, `envctl up --git-url --git-ref --git-subdir dockerhost`, health/readiness, `stream=false` 422, accepted chat, SSE smoke, worker/reaper logs, rollback previous SHA, and destroy cleanup steps where applicable。
  - Runbook is Chinese, operator-oriented and includes Git pull deployment, CLI dry-run/`--execute`, `--secret-env`, `--secret-file`, health/readiness checks, `stream=false` 422, SSE/WebSocket smoke, worker/reaper checks, same-environment redeploy, rollback to previous SHA, disposable cleanup and audit record。
  - Pytest contracts read the docs and CLI behavior and fail if required deployment gates, dry-run boundaries, action coverage, or secret-hygiene terms are removed。
- Edge cases:
  - Runbook must state that real secret values must not be printed, pasted, committed, copied into logs or included in audit artifacts。
  - Runbook must state that failed preflight/readiness/smoke/log checks block release completion。
  - Runbook must state that disposable env cleanup differs from long-lived data-bearing environment cleanup。
- Compatibility:
  - Existing production readiness doc remains untouched。
  - Existing DockerHost compose/template/env files remain untouched。
  - Tests do not require DockerHost, network, Docker daemon, provider credentials or local secret files。
- Operational:
  - Operators can follow one document to deploy, validate, redeploy, rollback and clean up。
  - Audit checklist preserves source of truth without leaking credentials。
- Evidence artifacts:
  - New spec file。
  - New implementation plan。
  - New runbook。
  - New CLI script。
  - New CLI pytest output。
  - Focused pytest output。
  - Spec/harness workflow checker output。

## Review Notes

- Open questions:
  - Final production auth/tenant and managed observability workflows remain outside this slice。
  - Future schema migrations may require rollback-specific migration policy beyond "redeploy previous SHA"; this runbook flags the compatibility check but does not design migration tooling。
- Accepted assumptions:
  - DockerHost Git pull deployment from pushed Git refs is the current self-service deployment model。
  - `envctl` one-shot secret injection can require passing secret arguments again during redeploy/rollback。
  - Dedicated smoke identity is sufficient for release validation until formal auth is added。
- Rejected alternatives:
  - Rejected embedding local token values or provider keys in the runbook。
  - Rejected relying on chat transcript instructions instead of repository docs plus tests。
  - Rejected broad `envctl logs` or unbounded tailing as default verification; bounded tails are enough for release gate evidence。
- Reviewer findings and resolution:
  - Pending implementation review。
