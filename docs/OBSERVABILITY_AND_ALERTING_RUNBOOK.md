# Chat Server 生产观测与告警 Runbook

## 适用范围

本 runbook 给内部运维和值守 Agent 使用,覆盖 Chat Server 生产观测、Grafana MCP 日志查询、核心面板、告警阈值、可提交观测资产、排障路径和秘密脱敏边界。

它补充 `docs/PRODUCTION_READINESS_RUNBOOK.md`,不替代部署、回滚、备份或 release gate。遇到需要改配置、回滚、扩容、停 worker、切 provider 的动作时,先形成证据并取得明确操作确认。

## 安全前置条件

- Grafana MCP endpoint: `https://grafana-mcp.openclaw-ai.cc`
- 查询前先确认授权 source,当前支持 `btcfun` 和 `merlinchain`。
- 本机可用时从私有路径加载环境变量;其他执行环境使用等价的安全 secret 注入:

```bash
source /Users/chris/.codex-local/observability/grafana_mcp_env.sh
```

- 只使用匹配 source 的 token 环境变量,例如 `OBS_MCP_TOKEN_BTCFUN_TEST` 或 `OBS_MCP_TOKEN_MERLINCHAIN_TEST`。
- 不要打印 token。不要 `echo` token,不要把 token 放进 prompt、PR、issue、日志、截图、文档或 shell history。
- 不要开启会回显命令和变量的调试模式。禁止在带 token 的 shell 里使用 `set -x`。
- 不要复制原始未脱敏生产日志。Grafana MCP 返回的日志正文以 `line_redacted` 为准。
- 如果工具输出中出现 secret,停止引用该内容,只记录“观察到敏感输出,已脱敏处理”和非敏感 metadata。

## 推荐日志查询

优先使用 bounded `POST /v1/logs`。每次查询必须明确 `source`、`service`、`env`、`time`、`limit`。默认时间窗口从 `now-15m` 到 `now`,默认 `limit` 不超过 `200`。

```bash
curl -fsS "$GRAFANA_MCP_BASE_URL/v1/logs" \
  -H "Authorization: Bearer $OBS_MCP_TOKEN_BTCFUN_TEST" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "btcfun",
    "service": "<chat-api-or-worker-service>",
    "env": "prod",
    "time": {"from": "now-15m", "to": "now"},
    "limit": 200,
    "filters": {
      "level": "error",
      "route": "/chat"
    }
  }'
```

查询结果使用方式:

- 只引用 `line_redacted`、timestamp、level、service、env、trace_id、run_id、status code、metric-like counts。
- 不引用 Authorization header、X-API-Key、provider key、DB/Redis URL、cookie、raw prompt、raw model response。
- 记录查询证据时写: source、service、env、time window、limit、过滤条件、聚合结论、下一步。

短时 live investigation 才使用 `GET /v1/logs/tail`,并且要设置明确 observation window,完成后停止。避免 broad LogQL,例如 `{job=~".+"}`;除非是小 limit 的 smoke test 且有明确原因。

常用 bounded 查询模板:

```json
{
  "source": "btcfun",
  "service": "<chat-api>",
  "env": "prod",
  "time": {"from": "now-30m", "to": "now"},
  "limit": 200,
  "filters": {"status": "5xx"}
}
```

```json
{
  "source": "btcfun",
  "service": "<chat-worker>",
  "env": "prod",
  "time": {"from": "now-30m", "to": "now"},
  "limit": 200,
  "filters": {"event": "provider_error"}
}
```

```json
{
  "source": "btcfun",
  "service": "<chat-reaper>",
  "env": "prod",
  "time": {"from": "now-1h", "to": "now"},
  "limit": 100,
  "filters": {"event": "reaper_scan"}
}
```

## 核心面板

| 面板 | 主要信号 | 观察方式 | 异常含义 |
| --- | --- | --- | --- |
| 请求量 | `chat_requests_total`, HTTP request count, `/chat` accepted count | 按 route、status、runtime_mode、provider、model 分组 | 流量突增会放大 provider quota、queue 和 TTFT 问题 |
| 错误率 | HTTP 5xx/4xx, stream error event, run failed terminal state | 5m/10m error ratio, 按 route/provider/runtime_mode 分组 | 用户可见失败、provider fail-closed、依赖不可用 |
| TTFT | `chat_ttft_seconds` p50/p95/p99 | 按 provider、model、runtime_mode 分组 | provider 变慢、queue wait、DB/Redis 变慢或 streaming stall |
| 流式 token gap | token delta 间隔 p95/p99, last-token age, stream stall/error | 从 stream metrics 或 redacted stream logs 聚合 | 已 accepted 但用户长时间看不到 token |
| provider 429/5xx | `provider_errors_total`, provider backoff, rate-limit decisions | 按 provider/model/status 分组 | quota 不足、供应商异常、backoff 正在保护系统 |
| Celery 队列 | queue depth, oldest queued age, active/reserved/retry/failures | worker metrics 或 redacted worker logs | batch 积压、worker 不消费、任务重试风暴 |
| reaper | `reaper_runs_total`, `reaper_requeued_total`, `reaper_failed_total`, last successful scan age | reaper metrics 和 `event=reaper_scan` logs | stale run 无法收敛、reaper 停止或失败 |
| readiness | `/readyz.checks.db`, `redis`, `event_bus`, `provider_secret`, `provider_limiter`, `reaper` | `/readyz` 与 dependency logs | 接流量前置条件不满足 |

如果某个面板缺数据,状态记为 `unknown`,并通过 `/readyz` 与 bounded logs 交叉验证。不要把“没有数据”当成健康。

## 可提交观测资产与离线校验

本仓库提交两类观测资产,供生产 observability owner 在外部 Grafana/Prometheus 流程中导入:

- Grafana dashboard JSON: `ops/observability/chat_server_overview_dashboard.json`
- Prometheus alert rules YAML: `ops/observability/chat_server_alert_rules.yml`

这些资产不包含真实 datasource secret、Grafana token、Prometheus 凭据、Alertmanager receiver 或生产日志原文。生产导入时需要由 owner 绑定实际 Prometheus datasource UID、`env`/`job` labels、rule group 加载位置和 Alertmanager routing。

提交前必须离线校验资产结构和 secret hygiene:

```bash
.venv/bin/python scripts/validate_observability_assets.py
```

完整 focused 验证:

```bash
.venv/bin/python -m pytest tests/test_observability_alerting_runbook_contract.py tests/test_observability_assets.py -q
```

Validator 的职责:

- 校验 dashboard JSON 可解析,包含 `Chat Server Observability` title、固定 uid、必需 panels 和 Prometheus expressions。
- 校验 alert rules YAML 包含 `chat-server-observability` group、必需 alerts、`expr`、`for`、`severity`、`annotations` 和 `runbook_url`。
- 校验资产覆盖请求量、错误率、TTFT、stream token gap、provider 429/5xx、Celery、reaper、readiness 的 metric family。
- 拒绝明显 secret-like literal,例如 raw bearer token、常见 provider API key 形状、private key marker、token assignment 或 inline credential。

Dashboard 中的 `chat_requests_total`、`chat_ttft_seconds_*`、`provider_errors_total`、`provider_rate_limit_decisions_total`、`redis_stream_events_total`、`reaper_*` 与当前 runtime/readiness 口径对齐。`chat_stream_token_gap_seconds_*`、`celery_queue_depth`、`celery_oldest_queued_age_seconds`、`chat_readyz_check` 是生产采集层或后续 runtime instrumentation 需要提供的 metric family;缺失时面板应显示 unknown,不得解释为健康。

## 告警规则

Prometheus rules 的仓库资产是 `ops/observability/chat_server_alert_rules.yml`。下面表格是 operator-facing 合同;YAML 中每条 alert 必须保留 severity、PromQL expression、持续时间和 `docs/OBSERVABILITY_AND_ALERTING_RUNBOOK.md` runbook annotation。

| 严重级别 | 条件 | 持续时间 | 首要排障路径 |
| --- | --- | --- | --- |
| P0 | 疑似 secret/token 出现在日志、prompt、PR、issue 或截图 | 任意一次 | 立即进入“疑似 secret 泄漏”路径 |
| P0 | 全部实例 `/readyz` 不 ready 或核心依赖不可用 | 2m | “readiness 失败”路径 |
| P0 | 用户可见 API 5xx > 5% | 5m | “API 错误率升高”路径 |
| P0 | 大多数 realtime runs 出现 stream stall,没有 token 或 terminal event | 5m | “TTFT 或流式 token gap 升高”路径 |
| P1 | 单环境 `/readyz` not ready | 2m | “readiness 失败”路径 |
| P1 | API 5xx > 2% | 5m | “API 错误率升高”路径 |
| P1 | TTFT p95 > 10s | 10m | “TTFT 或流式 token gap 升高”路径 |
| P1 | 流式 token gap p95 > 15s | 5m | “TTFT 或流式 token gap 升高”路径 |
| P1 | provider 5xx > 2% 或 provider 429 导致 admitted runs failed | 10m | “provider 429/5xx”路径 |
| P1 | Celery oldest queued age > 300s | 10m | “Celery 队列积压”路径 |
| P1 | reaper 超过 2 个 interval 没有 successful scan | 2 intervals | “reaper 或 stale run”路径 |
| P2 | TTFT p95 > 5s | 10m | 观察 provider、queue、DB/Redis latency |
| P2 | provider 429 > 5/min | 10m | 检查 quota、admission、backoff |
| P2 | Celery queue depth > 100 | 10m | 检查 worker active/reserved/retry |
| P2 | metrics scrape stale 或核心面板空白 | 5m | 检查 metrics endpoint、dashboard scrape、日志 fallback |

阈值上线后应根据真实 traffic baseline 调整。调整阈值前记录当前 baseline、误报/漏报样本和业务影响。

## 排障路径

### readiness 失败

1. 请求 `/readyz`,记录 `status` 和 `checks`,不要记录 secret 值。
2. 若 `db` 或 `redis` 异常,查询对应 service 最近 15m redacted logs。
3. 若 `provider_secret=missing`,检查 secret 注入是否缺失,不要打印 token 或 provider key。
4. 若 `provider_limiter=unavailable`,检查 Redis/provider limiter 初始化日志。
5. 若 `reaper=disabled`,确认是否为预期配置;生产默认应有 reaper 观测。

### API 错误率升高

1. 对比请求量和错误率是否与部署时间重合。
2. 用 bounded `/v1/logs` 查询 `<chat-api>` 最近 15m error logs,limit 200。
3. 按 route、status、error code、provider、runtime_mode 聚合。
4. 若错误集中在 provider,转到 provider 429/5xx。
5. 若错误集中在 stream/replay,检查 stream gap 和 Redis readiness。

### TTFT 或流式 token gap 升高

1. 观察 `chat_ttft_seconds` p95/p99 和 token gap p95/p99。
2. 切分 realtime 与 batch,再切分 provider/model。
3. 查询 `<chat-api>` stream logs 和 `<chat-worker>` provider call logs,使用 run_id/trace_id 关联。
4. 若 provider latency 同步升高,转 provider 429/5xx。
5. 若 queue wait 升高,转 Celery 队列积压。
6. 若只有 stream gap 升高,检查 Redis Stream、event bus、client disconnect/replay gap。

### provider 429/5xx

1. 观察 provider errors、backoff、rate-limit decisions、usage missing。
2. 查询 provider error redacted logs,按 provider/model/status 聚合。
3. 429: 检查 quota、RPM/TPM 配置、admission 是否 fail-closed、是否需要降并发或批处理。
4. 5xx: 检查 provider status、重试/降级策略、是否需要切 mock 仅做 smoke。
5. 不要在日志、ticket 或 prompt 中粘贴 provider request header、API key 或 raw response。

### Celery 队列积压

1. 观察 queue depth、oldest queued age、active/reserved/retry/failures。
2. 查询 `<chat-worker>` 最近 30m redacted logs,limit 200。
3. 检查 worker 是否在线、是否反复重启、是否 stuck 在 provider 或 DB/Redis。
4. 若积压来自 provider backoff,先处理 provider。
5. 若积压来自 worker capacity,再评估扩容或临时降级到 batch-only 的影响。

### reaper 或 stale run

1. 观察 last successful scan age、`reaper_runs_total`、`reaper_requeued_total`、`reaper_failed_total`。
2. 查询 `<chat-reaper>` 最近 1h `event=reaper_scan` redacted logs。
3. 若 reaper 停止,检查 service health 和启动配置。
4. 若 reaper failed 增长,按 sanitized reason 聚合,再关联 DB/Redis/provider。
5. 若 stale run 仍增长,检查 run terminal state 写入、stream terminal event 和 worker/realtime timeout。

### RAG/pgvector 依赖异常

1. 只在 Chat 请求实际使用 RAG 或 RAG smoke 时进入此路径。
2. 查询 RAG API/worker redacted logs,按 knowledge_base_id、job_id、status 聚合。
3. 检查 pgvector extension、embedding provider、ingestion job status。
4. 不要输出文档原文或 embedding provider secret。

### 疑似 secret 泄漏

1. 停止复制或引用可疑内容。
2. 记录非敏感 metadata: source、service、env、time window、field name、出现次数。
3. 通知 owner 执行 secret rotation 和日志清理流程。
4. 检查是否涉及 Grafana token、DockerHost token、provider API key、Authorization header、X-API-Key、DB/Redis password、private key。
5. 事件完成前不要把可疑原文写入 PR、issue、docs、prompt、release notes。

## Handoff Evidence

每次 incident 或 release smoke handoff 至少包含:

- source/service/env/time window/limit。
- dashboard 状态:请求量、错误率、TTFT、stream token gap、provider 429/5xx、Celery 队列、reaper、readiness。
- bounded log query 的聚合结论,只使用 `line_redacted` 或 metadata。
- 初步影响范围:用户、route、provider、runtime_mode、时间段。
- 已执行动作和未执行动作。
- 下一步建议和需要人工确认的操作。

不得包含 token、secret、raw Authorization header、raw prompt、raw model response、未脱敏日志原文。
