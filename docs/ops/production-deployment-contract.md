# Production Deployment Contract

本文是 general-agent-ai 采用的生产部署唯一运维契约。所有涉及 Dockerfile、docker-compose 文件、.env.example、Jenkinsfile、部署脚本、生产环境变量或生产发布行为的改动都必须先遵守本文件。

## 1. 环境边界

- 正式生产由 Jenkins 和 Docker Compose 管理。
- 生产入口固定为根目录 docker-compose-prd.yml。
- dockerhost/ 与根目录 docker-compose.yml 继续服务 dev/test/临时演练，不得因生产适配而改变。
- 环境差异只能通过独立 compose、Jenkins 渲染后的 .env 和运维配置表达。

## 2. 生产目录与命令

Jenkins 将仓库构建上下文、渲染后的 .env 和发布所需文件放到：

    /data/general-agent-ai

Jenkins 在该目录执行：

    docker compose --env-file .env -f docker-compose-prd.yml up -d --build --remove-orphans

仓库必须提供：

- docker-compose-prd.yml
- .env.example
- dockerhost/Dockerfile
- .dockerignore

Jenkinsfile、生产主机编排、凭据存储、流量入口和 Security Group 由运维侧维护，不在本仓库中复制。

## 3. Production Compose

### 3.1 服务

稳定服务名为 api、worker、reaper 和 migrate。

- api、worker、reaper 必须前台运行并显式使用 restart: unless-stopped。
- migrate 是一次性迁移任务，必须成功后才启动长驻服务。
- 所有服务通过 env_file: .env 接收运行时配置。
- 只有 api 可以发布宿主机端口。

Postgres/pgvector 与 Redis 是生产外部依赖。DB_URL、REDIS_URL、CELERY_BROKER_URL 和 CELERY_RESULT_BACKEND 必须由运维注入。数据库与 Redis 的供应商、网络、备份、保留、容灾和回滚兼容性由运维确认，本仓库不擅自定义生产数据拓扑。

### 3.2 HTTP 端口

api 的端口模板固定为：

    "${APP_BIND_ADDR:?APP_BIND_ADDR is required}:${APP_PORT:-8080}:8080"

.env.example 必须包含：

    APP_BIND_ADDR=${APP_BIND_ADDR}
    APP_PORT=${APP_PORT}

APP_BIND_ADDR 不允许默认值。运维根据入口选择 0.0.0.0、127.0.0.1 或实例私网 IP，并通过 Security Group 或本机反代限制来源。compose 不得写死 0.0.0.0:8080:8080 或 127.0.0.1:8080:8080。

数据库、Redis、worker、reaper 和 migrate 不得发布宿主机端口。

### 3.3 日志与健康检查

业务日志必须写 stdout / stderr，由 Promtail 采集 Docker 日志；不得要求宿主机日志文件挂载。

所有长驻服务使用 Docker 日志滚动：

    max-size: "100m"
    max-file: "3"

api healthcheck 请求容器内 http://localhost:8080/healthz，间隔 10 秒、超时 3 秒、重试 12 次、启动宽限 20 秒。发布验收还必须检查 /readyz。

## 4. Jenkins Environment Template

.env.example 是 Jenkins 生产渲染模板，不是本地开发模板。env.local.example 才用于本地快速启动。

.env.example 必须覆盖：

- app.core.config.Settings 的每一个环境字段；
- docker-compose-prd.yml 的每一个变量；
- APP_BIND_ADDR 与 APP_PORT。

下列值必须使用同名 ${KEY} 占位符：

- 数据库、Redis、Celery 连接串；
- provider、embedding 或第三方 API key；
- secret/key-pool 文件路径；
- 私有 Marketplace endpoint；
- 内部用户、知识库或管理身份配置；
- 任何 password、token、secret 或 private key。

非敏感且明确的生产默认值可以直接写入。provider/model 选择和其他随环境变化的值应由 Jenkins 渲染。

真实 .env 不得进入 Git。.gitignore 必须包含：

    .env
    .env.*
    !.env.example

## 5. Image Build

生产 compose 使用仓库根目录作为 build context，并使用 dockerhost/Dockerfile。Dockerfile 不得 COPY 或 ADD 真实 .env。

由于 Dockerfile 使用 COPY .，根目录 .dockerignore 至少排除：

    .git
    .env
    .env.*
    !.env.example
    __pycache__
    .pytest_cache
    .mypy_cache
    .ruff_cache
    node_modules
    dist
    build
    *.tar.gz

容器入口必须是明确的前台进程。生产 compose 使用 /usr/local/bin/python 作为 api、worker、reaper 和 migrate 的可执行入口。

## 6. 数据与持久化

应用容器内数据视为临时数据，不声明应用数据 volume。生产持久数据位于外部 Postgres/pgvector 与 Redis；运维必须在首次发布前确认：

- endpoint、凭据和网络连通；
- Postgres extension/migration 权限；
- 备份、恢复、保留和监控；
- 上一版本与当前 schema/data shape 的回滚兼容性。

不得挂载 /、/root、/etc 或其他宿主机敏感目录。

## 7. Jenkins Contract

Jenkins 流程依次：

1. checkout 已批准的 Git ref；
2. 读取 .env.example 与 Jenkins 私有配置；
3. 将每个 ${KEY} 渲染为对应值并生成未提交的 .env；
4. 确认没有未解析占位符；
5. 将发布文件推送到 /data/general-agent-ai；
6. 在目标目录执行标准 compose 命令；
7. 验证容器状态、/healthz、/readyz、异步 chat/SSE 和 worker/reaper；
8. 保存不含 secret 的 ref、SHA、状态码和 smoke 结果。

## 8. 修改后检查

运行：

    .venv/bin/python scripts/check_production_deployment_contract.py
    docker compose --env-file <rendered-test-env> -f docker-compose-prd.yml config
    VERIFY_COMPARE_REF=<base> make verify-change

检查结果必须证明：

- 所有要求文件存在；
- .env.example 覆盖运行时和 compose 变量；
- 敏感值仅为占位符；
- .env 不进入 Git 或镜像；
- api 使用 APP_BIND_ADDR / APP_PORT 模板并有 healthcheck；
- 内部服务不发布端口；
- 日志保持 stdout / stderr；
- dockerhost/ 与本地 compose 没有行为变化。

## 9. 合并前清单

- [ ] docker-compose-prd.yml、.env.example、dockerhost/Dockerfile、.dockerignore 存在。
- [ ] 标准命令可在 /data/general-agent-ai 执行。
- [ ] Jenkins 私有配置覆盖所有 ${KEY}，且渲染后没有未解析占位符。
- [ ] APP_BIND_ADDR 的实际值和 Security Group/反代路径已由运维确认。
- [ ] 外部 Postgres/pgvector、Redis、备份和回滚策略已由运维确认。
- [ ] provider/model、所有 secret 与 Marketplace 私有 endpoint 已由运维注入。
- [ ] /healthz、/readyz、异步 chat/SSE、worker 和 reaper smoke 通过。
- [ ] dev/test DockerHost 与本地启动流程未被修改。
