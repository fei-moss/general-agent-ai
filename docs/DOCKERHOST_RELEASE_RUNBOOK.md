# DockerHost 发布与回滚 Runbook

Spec: `SPEC-DOCKERHOST-RELEASE-RUNBOOK-001`

正式生产由 Jenkins / `docker-compose-prd.yml` 管理并遵循 `docs/ops/production-deployment-contract.md`；本 runbook 只管理现有 dev/test/临时 DockerHost 环境。

本 runbook 面向内部运维和授权 Agent,用于在 DockerHost 上执行 `general-agent-ai` 的 Git pull deployment、同环境 redeploy、回滚、清理和审计。这里不包含任何真实 secret。

## 0. 安全边界

- 不要打印、粘贴、提交、复制或写入审计记录:
  - `ENVCTL_TOKEN`
  - provider key,例如 `ZAI_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
  - bearer token、private key、secret file 内容
- 不要在 shell 中开启 `set -x` 后执行 secret 注入命令。
- 不要使用会把明文值留在 shell history 或平台日志里的 `--secret KEY=VALUE`。
- 只记录 secret 名称或 secret file 类别,不要记录 secret 值。
- 本仓库只保存 runbook、spec、plan 和测试;本地凭据文件必须保留在仓库外。

## 1. envctl 前置条件

在本机私有 shell 中加载 DockerHost 凭据。路径由本机 runbook 或 `AGENTS.md` 指定,不要把该文件内容复制到仓库。

```bash
export ENVCTL_ENV_FILE=<path-to-private-envctl-env-file>
source "$ENVCTL_ENV_FILE"

envctl version
envctl templates
envctl hosts
envctl topology
```

如果 `envctl` 不存在,按 DockerHost 官方安装方式安装预编译 CLI,不要克隆控制面仓库到项目目录。

## 2. 发布输入

先明确环境名、Git URL 和候选 ref。Git ref 必须已经推送到远端,因为 DockerHost 当前部署模型是 Git pull deployment。

```bash
export PROJECT_DIR=/Users/chris/AiProject/general-agent-ai
export ENV_NAME=<owner>-general-agent-ai-rag
export GIT_URL=git@github.com:fei-moss/general-agent-ai.git
export GIT_REF=<branch-or-sha>
export BASE_URL=https://<api-domain>
export PRODUCTION_MODE=true
export ALLOW_MOCK_PROVIDER=false
export CHAT_RUNTIME_MODE=auto
export LLM_PROVIDER=zai
export PRODUCTION_MODE=true
export ALLOW_MOCK_PROVIDER=false
export ZAI_MODEL=glm-5.2
export ZAI_THINKING_TYPE=disabled
export ZAI_REASONING_EFFORT=low
export ZAI_TOOL_STREAM=true
export GEMINI_MODEL=gemini-2.5-flash
export RAG_ENABLED=true
export RAG_VECTOR_STORE=pgvector
export RAG_ADMIN_USER_IDS=<rag-admin-user-id>
export RAG_DEFAULT_KNOWLEDGE_BASE_ID=<default-kb-id>
export RAG_INTERNAL_OWNER_USER_ID=<rag-owner-user-id>
export RAG_ALLOW_CLIENT_KNOWLEDGE_BASE_ID=false
export EMBEDDING_PROVIDER=gemini
export EMBEDDING_MODEL=gemini-embedding-2
export EMBEDDING_DIM=256
export PROVIDER_DEFAULT_RPM=60
export PROVIDER_DEFAULT_TPM=60000
export PROVIDER_DEFAULT_MAX_OUTPUT_TOKENS=4096
export RUN_MAX_RUNTIME_S=300
export STREAM_MAXLEN=1000
export STREAM_TTL_S=86400
export METRICS_ENABLED=true
export REAPER_ENABLED=true
export REAPER_INTERVAL_S=30
export REAPER_STALE_AFTER_S=300
export REAPER_MAX_ATTEMPTS=3
export WORKER_POOL=prefork
export WORKER_CONCURRENCY=2
export MARKETPLACE_AI_BASE_URL=http://app.df-moss-site-agent-marketplace-dev.dockerhost:8081

git -C "$PROJECT_DIR" status --short
git -C "$PROJECT_DIR" rev-parse HEAD
git ls-remote "$GIT_URL" "$GIT_REF"
```

如果 `git status --short` 显示和本次发布无关的改动,先停下来确认,不要把并行 worker 的文件当成本次发布内容处理。

## 3. 发布前门禁

每次发布或 redeploy 前先验证 DockerHost adapter。任一命令失败都不得继续部署。

```bash
envctl check-project --dir /Users/chris/AiProject/general-agent-ai
envctl validate-template --dir /Users/chris/AiProject/general-agent-ai/dockerhost
envctl status --name "$ENV_NAME" # must report connectivity group internal-connect and stable internal endpoints
```

可选本地结构检查:

```bash
docker compose -f /Users/chris/AiProject/general-agent-ai/dockerhost/compose.yaml config
```

## DockerHost Release CLI（默认 dry-run）

`scripts/dockerhost_release.py` 是本 runbook 的辅助 CLI。默认只生成有序 plan 和脱敏 audit JSON,不会调用真实 `git`, `envctl` 或 `curl`。只有显式加入 `--execute` 时,CLI 才会执行外部命令。

deploy/redeploy/rollback 会把脚本声明的生产运行配置名自动转换为 DockerHost 的
`--secret-env <NAME>` 参数。初次 deploy 使用 `envctl up`；已有长驻环境的 redeploy
和 rollback 使用 `envctl branch-space switch --deploy=false` 后再执行
`envctl branch-space deploy`。`--execute` 会在调用 DockerHost 前拒绝任何缺失或
空值；默认也拒绝 mock provider，只有明确的非生产/紧急回滚才可使用
`--allow-mock`。因此不要绕过此 CLI 直接依赖 Compose 默认值。

dry-run deploy plan:

```bash
.venv/bin/python scripts/dockerhost_release.py deploy \
  --name "$ENV_NAME" \
  --git-url "$GIT_URL" \
  --git-ref "$GIT_REF" \
  --connectivity-group internal-connect \
  --base-url "$BASE_URL" \
  --secret-env ZAI_API_KEY \
  --secret-file GEMINI_API_KEY=<path-to-private-gemini-key-file> \
  --audit-json /tmp/dockerhost-release-plan.json
```

真实执行必须显式添加 `--execute`;执行结果和命令输出会写入脱敏 audit JSON:

```bash
.venv/bin/python scripts/dockerhost_release.py deploy \
  --name "$ENV_NAME" \
  --git-url "$GIT_URL" \
  --git-ref "$GIT_REF" \
  --connectivity-group internal-connect \
  --base-url "$BASE_URL" \
  --secret-env ZAI_API_KEY \
  --secret-env GEMINI_API_KEY \
  --execute \
  --audit-json /tmp/dockerhost-release-audit.json
```

其他 action:

```bash
.venv/bin/python scripts/dockerhost_release.py redeploy \
  --name "$ENV_NAME" \
  --git-url "$GIT_URL" \
  --git-ref "$GIT_REF" \
  --base-url "$BASE_URL" \
  --secret-env ZAI_API_KEY

.venv/bin/python scripts/dockerhost_release.py rollback --previous-sha "$PREVIOUS_SHA" \
  --name "$ENV_NAME" \
  --git-url "$GIT_URL" \
  --base-url "$BASE_URL" \
  --secret-env ZAI_API_KEY

.venv/bin/python scripts/dockerhost_release.py smoke \
  --name "$ENV_NAME" \
  --base-url "$BASE_URL"

.venv/bin/python scripts/dockerhost_release.py destroy \
  --name "$ENV_NAME"
```

CLI plan/execute 顺序:

- deploy: `git status --short`, `git rev-parse HEAD`, `git ls-remote`, `envctl check-project`, `envctl validate-template`, `envctl up --git-url ... --git-ref ... --git-subdir dockerhost`,然后执行统一 smoke。
- redeploy/rollback: 相同 preflight 后先更新 branch-space connectivity，再用 `envctl branch-space switch --name ... --git-ref ... --deploy=false` 选择目标 ref，最后运行带完整一次性配置的 `envctl branch-space deploy --name ...`，然后执行统一 smoke。
- 统一 smoke: `envctl status`, `/healthz`, `/readyz`, `stream=false` 422, accepted chat, SSE smoke, `/runs/{agent_run_id}`, worker logs, reaper logs。
- The release CLI defaults `--connectivity-group internal-connect`; status must retain that membership. Every deploy exports and passes `MARKETPLACE_AI_BASE_URL` with the internal Marketplace DNS. Public Marketplace URLs are forbidden for this setting.
- rollback 使用 `--previous-sha` 作为 branch-space switch 的目标,并复用同一环境和 secret 注入方式。
- smoke 只执行状态、健康、ready、async chat、SSE 和 worker/reaper 检查,不改变 Git ref。
- destroy 只规划或执行 `envctl unexpose --service db`, `envctl unexpose --service cache`, `envctl down --name "$ENV_NAME"`;只对 disposable environment 使用。

Secret hygiene:

- `--secret-env` 只接受 secret 名称,例如 `ZAI_API_KEY`;不要传 `ZAI_API_KEY=<value>`。
- `--secret-file KEY=PATH` 只在真实 envctl 命令中使用 PATH;audit/stdout 只记录 secret 名称和 `KEY=<redacted-secret-file>`。
- CLI 不支持 `--secret KEY=VALUE`。
- command output 和 audit JSON 都必须脱敏;发现 secret 值、raw bearer token、private key 或 secret file 内容时,不得把 audit 作为发布证据提交。
- CLI 只覆盖 SSE smoke;需要 WebSocket 证据时继续执行本 runbook 的 WebSocket Smoke 章节。

## 4. Secret 注入

优先使用 `--secret-env`。这要求 secret 值已在当前私有 shell 环境中存在,但不要用 `env`, `printenv`, `set`, `history` 或日志输出它们。

```bash
export LLM_PROVIDER=zai
export ZAI_MODEL=glm-5.2
export ZAI_THINKING_TYPE=disabled
export ZAI_REASONING_EFFORT=low
export ZAI_TOOL_STREAM=true
export GEMINI_MODEL=gemini-2.5-flash
export CHAT_RUNTIME_MODE=auto
export RAG_ENABLED=true
export RAG_VECTOR_STORE=pgvector
export RAG_ADMIN_USER_IDS=<rag-admin-user-id>
export RAG_DEFAULT_KNOWLEDGE_BASE_ID=<default-kb-id>
export RAG_INTERNAL_OWNER_USER_ID=<rag-owner-user-id>
export RAG_ALLOW_CLIENT_KNOWLEDGE_BASE_ID=false
export EMBEDDING_PROVIDER=gemini
export EMBEDDING_MODEL=gemini-embedding-2
export EMBEDDING_DIM=256
export PROVIDER_DEFAULT_RPM=60
export PROVIDER_DEFAULT_TPM=60000
export PROVIDER_DEFAULT_MAX_OUTPUT_TOKENS=4096
export RUN_MAX_RUNTIME_S=300
export STREAM_MAXLEN=1000
export STREAM_TTL_S=86400
export METRICS_ENABLED=true
export REAPER_ENABLED=true
export REAPER_INTERVAL_S=30
export REAPER_STALE_AFTER_S=300
export REAPER_MAX_ATTEMPTS=3
export WORKER_POOL=prefork
export WORKER_CONCURRENCY=2
export MARKETPLACE_AI_BASE_URL=http://app.df-moss-site-agent-marketplace-dev.dockerhost:8081

.venv/bin/python scripts/dockerhost_release.py deploy \
  --name "$ENV_NAME" \
  --git-url "$GIT_URL" \
  --git-ref "$GIT_REF" \
  --connectivity-group internal-connect \
  --base-url "$BASE_URL" \
  --secret-env ZAI_API_KEY \
  --secret-env GEMINI_API_KEY \
  --execute
```

当平台或操作习惯要求文件注入时,使用 `--secret-file KEY=PATH` 指向仓库外的私有文件。路径可以进入命令记录,文件内容不可以。

```bash
.venv/bin/python scripts/dockerhost_release.py deploy \
  --name "$ENV_NAME" \
  --git-url "$GIT_URL" \
  --git-ref "$GIT_REF" \
  --connectivity-group internal-connect \
  --base-url "$BASE_URL" \
  --secret-file ZAI_API_KEY=<path-to-private-zai-key-file> \
  --secret-file GEMINI_API_KEY=<path-to-private-gemini-key-file> \
  --execute
```

如果 DockerHost 对本环境的 secret 是一次性注入,同环境 redeploy 或 rollback 时也要重新传入相同的 `--secret-env` 或 `--secret-file` 参数。

## 5. Git Ref Deploy

初次部署由 CLI 调用 `envctl up`。同环境 redeploy/rollback 只支持已登记的
branch-space，由 CLI 切换其 Git ref 后调用 branch-space deploy。发布记录中保留
环境名、Git URL、Git ref 和解析后的 commit SHA。

```bash
.venv/bin/python scripts/dockerhost_release.py deploy \
  --name "$ENV_NAME" \
  --git-url "$GIT_URL" \
  --git-ref "$GIT_REF" \
  --base-url "$BASE_URL" \
  --secret-env ZAI_API_KEY \
  --secret-env GEMINI_API_KEY \
  --execute

envctl status --name "$ENV_NAME"
```

长驻 branch-space 的底层命令形态如下；生产操作仍应通过 release CLI 生成完整参数:

```bash
envctl branch-space switch --name "$ENV_NAME" --git-ref "$GIT_REF" --deploy=false
envctl branch-space deploy --name "$ENV_NAME"
envctl branch-space status --name "$ENV_NAME"
```

`branch-space deploy` 的 `.env.generated` 只包含本次显式传入的值。生产发布必须
通过 release CLI 自动传入运行配置；不要直接运行不带完整 `--secret-env` 集合的
branch-space deploy。发布后必须以 `/readyz` 的真实 provider 状态验收，不能只看
容器 health。

## 6. 健康检查

从 `envctl status` 中取 `api` 域名并设置 `BASE_URL`。

```bash
export BASE_URL=https://<api-domain>

curl -fsS "$BASE_URL/healthz"
curl -fsS "$BASE_URL/readyz"
```

发布完成前必须满足:

- `/healthz` 返回 2xx。
- `/readyz` 返回 2xx。
- `/readyz` 不包含 provider key、`ENVCTL_TOKEN` 或任何 secret 值。
- `/readyz` 表示 DB、Redis、event bus、provider secret、provider limiter 均 ready。
- `/readyz` 的 `provider_secret` 必须为 `configured`；生产验收不得为 `mock`。
- 启用 RAG 时，`rag_vector_store` 必须为 `pgvector`，`embedding_provider` 必须为真实 provider；`memory/hash` 仅允许本地测试。
- API/worker/reaper 必须在一次性 `app.db.migrate` 服务成功后启动；迁移失败即停止发布。

可选支持证据:

```bash
curl -fsS "$BASE_URL/metrics" | head
```

## 7. Async Chat 合约 Smoke

先确认同步等待入口仍被拒绝。`stream=false` 必须返回 `422 STREAM_FALSE_NOT_SUPPORTED`;否则不得继续宣布发布成功。
运行本节命令前,先把 `AUTH_HEADER` 设置为 smoke 身份对应的完整认证 header。

```bash
curl -sS -o /tmp/stream_false.json -w "%{http_code}\n" \
  "$BASE_URL/chat" \
  -H 'Content-Type: application/json' \
  -H "$AUTH_HEADER" \
  -d '{"message":"smoke: stream=false must be rejected","stream":false}'

cat /tmp/stream_false.json
```

再执行 accepted chat smoke。记录 `agent_run_id`, `conversation_id`, `stream_url`, `ws_url`。

```bash
curl -fsS "$BASE_URL/chat" \
  -H 'Content-Type: application/json' \
  -H "$AUTH_HEADER" \
  -d '{"message":"用一句话回答: DockerHost chat smoke 是否连通?","stream":true,"metadata":{"release_smoke":true}}' \
  | tee /tmp/chat_accepted.json

export RUN_ID=$(jq -r '.agent_run_id' /tmp/chat_accepted.json)
export STREAM_URL=$(jq -r '.stream_url' /tmp/chat_accepted.json)
export WS_URL=$(jq -r '.ws_url' /tmp/chat_accepted.json)
```

## 8. SSE Smoke

SSE 必须能收到事件并最终进入 terminal state。若 SSE 连接中断,查询 `/runs/{agent_run_id}` 保留证据。

```bash
curl -N \
  -H "$AUTH_HEADER" \
  "$BASE_URL$STREAM_URL"

curl -fsS \
  -H "$AUTH_HEADER" \
  "$BASE_URL/runs/$RUN_ID"
```

通过标准:

- 能看到流式事件。
- 最终 run 状态为 `SUCCEEDED`,或失败时有明确、已脱敏错误。
- 输出和错误不包含 provider key 或 `ENVCTL_TOKEN`。

## 9. WebSocket Smoke

如果本机有 `websocat`,执行 WebSocket smoke:

```bash
websocat \
  -H "$AUTH_HEADER" \
  "$BASE_URL$WS_URL"
```

如果没有 `websocat`,记录缺失原因,但至少必须完成 SSE smoke 和 `/runs/{agent_run_id}` 查询。WebSocket smoke 失败且 SSE 正常时,仍需记录为发布风险,由负责人决定是否 rollback 或继续。

## 10. Worker 与 Reaper 验证

API ready 不代表后台执行链路 ready。发布或 rollback 后必须检查 worker 和 reaper。

```bash
envctl logs --name "$ENV_NAME" --service worker --tail 200
envctl logs --name "$ENV_NAME" --service reaper --tail 200
envctl logs --name "$ENV_NAME" --service api --tail 200
```

通过标准:

- worker 日志显示 Celery worker 已启动并处理队列,没有启动循环、secret missing 或连接失败。
- reaper 日志显示 `app.tasks.reaper` 周期或 dry-run 检查正常,没有连续失败。
- api 日志没有 provider key、`ENVCTL_TOKEN`、raw bearer token 或 private key。
- worker/reaper healthcheck 失败时,不得把发布标记为完成。

## 11. 同环境 Redeploy

同一个 branch-space `ENV_NAME` 可以 redeploy 到新的 branch 或 SHA。redeploy 之前
重新跑发布前门禁并确认该 ref 已推送。CLI 不会再次调用只允许创建新环境的
`envctl up`;它会先 switch ref（不隐式 deploy），再以完整一次性配置执行
branch-space deploy。

```bash
export GIT_REF=<new-branch-or-sha>

envctl check-project --dir /Users/chris/AiProject/general-agent-ai
envctl validate-template --dir /Users/chris/AiProject/general-agent-ai/dockerhost

.venv/bin/python scripts/dockerhost_release.py redeploy \
  --name "$ENV_NAME" \
  --git-url "$GIT_URL" \
  --git-ref "$GIT_REF" \
  --base-url "$BASE_URL" \
  --secret-env ZAI_API_KEY \
  --secret-env GEMINI_API_KEY \
  --execute
```

redeploy 后重复:

- `envctl status --name "$ENV_NAME"`
- `/healthz`
- `/readyz`
- `stream=false` 422
- SSE smoke
- WebSocket smoke 或风险记录
- worker/reaper logs

## 12. 回滚到上一 SHA

发布前记录上一 known-good SHA:

```bash
export PREVIOUS_SHA=<previous-known-good-sha>
```

如果候选发布失败,用同一 branch-space 回滚到上一 SHA。不要只切换本地分支;
CLI 必须执行 branch-space switch 与 deploy，使 DockerHost 实际运行目标 SHA。

```bash
.venv/bin/python scripts/dockerhost_release.py rollback \
  --previous-sha "$PREVIOUS_SHA" \
  --name "$ENV_NAME" \
  --git-url "$GIT_URL" \
  --base-url "$BASE_URL" \
  --secret-env ZAI_API_KEY \
  --secret-env GEMINI_API_KEY \
  --execute

envctl status --name "$ENV_NAME"
```

回滚完成条件:

- `/healthz` 通过。
- `/readyz` 通过。
- `stream=false` 返回 `422 STREAM_FALSE_NOT_SUPPORTED`。
- SSE smoke 通过。
- WebSocket smoke 通过或有明确风险记录。
- worker/reaper logs 无启动失败、secret missing 或连接失败。
- 审计记录包含失败 ref、rollback SHA、触发原因和验证结果。

如果失败发布包含 schema migration 或数据格式变更,回滚前必须额外确认上一 SHA 与当前 Postgres volume 兼容;不兼容时先停止切流并找负责人决策,不要直接销毁数据。

## 13. 清理 Disposable Environment

只对 disposable environment 执行销毁。长驻或承载真实数据的环境,先确认备份、迁移或负责人批准。

```bash
envctl unexpose --name "$ENV_NAME" --service db
envctl unexpose --name "$ENV_NAME" --service cache
envctl down --name "$ENV_NAME"
```

清理后记录:

- 环境名。
- destroy 时间。
- 是否存在临时 DB/cache exposure。
- 是否已取消 exposure。
- `envctl down` 结果。

## 14. 审计清单

每次 deploy、redeploy、rollback 或 destroy 后,记录以下非敏感证据:

- Operator 或 Agent 名称。
- 环境名 `ENV_NAME`。
- Git URL。
- Git ref 和解析后的 commit SHA。
- 部署类型: deploy、redeploy、rollback 或 destroy。
- secret 注入方式: `--secret-env` 或 `--secret-file`,只记录 secret 名称,不记录值。
- `envctl check-project` 结果。
- `envctl validate-template` 结果。
- `envctl status` 摘要。
- `/healthz` 状态码。
- `/readyz` 状态码和 ready 摘要。
- `stream=false` 422 结果。
- SSE smoke run id 与 terminal state。
- WebSocket smoke 结果或跳过原因。
- worker/reaper log 检查摘要。
- rollback 时的 previous SHA、失败 ref 和触发原因。
- disposable cleanup 时的 `envctl down` 结果。

审计内容不得包含 `ENVCTL_TOKEN`, provider key, raw bearer token, private key, secret file 内容或用户私有消息正文。
