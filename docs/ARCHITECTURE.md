# Agent Execution Platform 架构设计文档

> 高性能 AI Chat 执行平台。
> 技术栈: Python 3.10 / FastAPI / SQLAlchemy 2.0 async / Pydantic AI / Redis Stream / Postgres / Celery / SSE + WebSocket。
> 核心目标: 高并发、低 TTFT、实时流式响应、后台异步任务、水平扩展。

本文是本需求唯一架构沟通文档, 同时覆盖设计结论、Cloud 审查关注点、风险和第一阶段落地顺序。

---

## 0. 结论

当前平台的分层边界保持不变, 但执行模型按 workload 拆分:

- **实时交互式 Chat**: 默认走 FastAPI async 或独立 Async Runner 常驻事件循环, 直接执行 Pydantic AI `agent.iter()` / `run_stream_events()`。
- **慢任务 / 批任务**: 继续走 Queue / Celery Worker, 执行文件分析、长 RAG、慢工具、批量分析、可重试离线 Agent run。
- **事件热路径**: 从 Redis Pub/Sub 演进为 Redis Stream, 用 Stream id 做顺序和断线回放。
- **权威状态**: Postgres 保存 conversations、messages、runs、tool calls、final outputs、idempotency keys 和里程碑事件。

不再把“所有实时 Chat 默认入 Celery Worker”作为高性能目标架构。Celery prefork 更适合批处理和可靠性优先的后台任务, 不适合作为高并发低延迟实时流式 Chat 的默认执行引擎。

---

## 1. 设计目标

第一阶段压测目标先按下面口径校验, 后续可根据真实业务容量调整:

- 3000 路并发实时流下, TTFT p95 < 800ms。
- 单 Async Runner 进程承载 >= 1000 路并发 I/O-bound run。
- 实时路径不因 DB 连接池大小限制并发, 流式期间不持有 DB 连接。
- Redis Stream 写入和 SSE/WS 转发在目标并发下无持续堆积。

| 目标 | 设计手段 |
| --- | --- |
| 低 TTFT | 实时请求跳过 Celery broker 和 worker 调度, 由常驻 async event loop 执行 |
| 高并发 | I/O-bound LLM streaming 使用单事件循环挂大量 await, 不用进程数承载并发 |
| 水平扩展 | API、Async Runner、Worker 分开扩容; Runner 按 CPU 核数多进程部署 |
| 实时事件流 | Redis Stream + SSE/WebSocket |
| 断线回放 | Redis Stream `XRANGE` + `Last-Event-ID` |
| 后台可靠性 | Celery 处理慢任务、批任务和可重试任务 |
| 权威持久化 | Postgres 保存最终事实和审计数据 |
| 全局控制 | Redis 做限流、锁、semaphore、短状态 |

---

## 2. 总体架构

```text
Client
  |
  v
API Gateway / Load Balancer
  |
  +----------------------------------+
  |                                  |
  v                                  v
[实时交互式路径]                    [慢任务 / 批任务路径]
FastAPI API Service                 FastAPI API Service
  - auth / validation                 - auth / validation
  - create message/run                - create run/task
  - hold SSE/WS                       - enqueue
  |                                   |
  v                                   v
Async Runner                      Queue / Celery
  - resident event loop               |
  - high concurrency await            v
  |                                Worker Pool
  v                                   |
Pydantic AI Agent                     v
  |                                Pydantic AI Agent
  | streaming                         |
  v                                   v
Redis Stream                       Postgres
  - XADD events                    - final result
  - XREAD realtime
  - XRANGE replay
  |
  v
SSE / WebSocket
  |
  v
Postgres
  - messages
  - runs
  - tool calls
  - final outputs
  - milestone events
```

---

## 3. 分层职责

### 3.1 Gateway / Load Balancer

- TLS
- 入口路由
- 粗粒度限流
- request timeout
- SSE/WebSocket 长连接转发
- body size limit
- WAF / CORS 等边缘控制

Gateway 只做入口保护, 不执行 Agent。

### 3.2 FastAPI API Service

职责:

- 鉴权和参数校验
- 创建或复用 conversation
- 写入 user message
- 创建 agent_run
- 根据请求类型选择实时路径或后台路径
- SSE/WebSocket 连接承载和事件转发
- 状态查询和历史查询

FastAPI 本身保持无状态, 不保存权威会话内存。

### 3.3 Async Runner

实时 Chat 的默认执行引擎。

职责:

- 常驻 asyncio event loop
- 复用 HTTP client、Redis client、DB pool、provider client
- 执行 Pydantic AI `agent.iter()` / `run_stream_events()`
- 聚合 token 事件
- 写 Redis Stream
- 写 Postgres 最终状态
- 管理 cancellation 和 graceful shutdown
- 严格管理 DB 连接生命周期: 读历史后立即释放连接, LLM 流式期间不持有 DB session, 最终落库时重新获取连接
- 按 CPU 核数启动多个 Runner 进程, 每个进程一个事件循环; 进程间通过 Redis Stream、Postgres 和 Redis 锁解耦
- 为每个 RUNNING realtime run 维护 runner lease / heartbeat, 供 reaper 判断宿主进程是否仍存活

Async Runner 可以先内嵌在 FastAPI 进程中实现, 高并发阶段再拆成独立服务。

注意: 单事件循环只等于单核调度能力。LLM streaming 是 I/O-bound, 但 token 聚合、JSON 编解码、schema 校验、SSE 编码、工具分发仍会消耗 CPU。生产部署必须使用多个 Runner 进程吃满多核, 不能把高并发能力押在单进程单 loop 上。

### 3.4 Pydantic AI Runtime

职责:

- system prompt / instructions
- tool registration / tool calling
- structured output
- model streaming
- 单次 run 的 usage limits
- output schema 校验

不负责:

- 全局限流
- 分布式锁
- 幂等
- 任务调度
- 会话持久化
- 长任务恢复

### 3.5 Queue / Celery Worker

只处理后台任务:

- 文件分析
- 长 RAG
- 批量分析
- 慢工具调用
- 可离线执行的 Agent run
- 需要失败重试的任务

Celery 不再作为实时 Chat 默认执行路径。

### 3.6 Postgres

权威存储:

- users
- conversations
- messages
- agent_runs
- task_states
- tool_call_logs
- final outputs
- idempotency keys
- milestone events

Postgres 不写每个 token。实时 token 事件进入 Redis Stream, Postgres 只保存里程碑和最终结果。

实时路径必须遵守连接释放规则:

- 获取 DB 连接读取 conversation/history。
- 读取完成后立即关闭 session 或归还连接池。
- 执行 Pydantic AI / LLM streaming 期间不持有任何 DB 连接。
- 工具调用如需 DB, 按短事务获取并释放。
- 最终写 assistant message、tool_call_log 和 agent_run 状态时重新获取连接。

否则并发上限会从事件循环能力退化为 DB 连接池大小。

### 3.7 Redis

高并发控制面:

- Redis Stream 事件热路径和回放
- 用户级限流
- provider/model token bucket
- conversation lock
- runner semaphore
- run 快速状态
- Celery broker 或 queue buffer

Redis 不作为最终消息存储。

---

## 4. 请求路径

### 4.1 实时交互式 Chat

```text
Client POST /chat
  |
  v
FastAPI
  - auth / validation / rate limit
  - ensure conversation
  - acquire conversation lock
  - insert user message
  - create agent_run
  - start async run or dispatch to async runner
  |
  v
Async Runner
  - create run lease / heartbeat
  - load history, then release DB connection
  - run Pydantic AI agent.iter() / run_stream_events()
  - call model provider
  - call tools
  - aggregate token chunks
  - XADD events to Redis Stream
  |
  v
FastAPI SSE/WS
  - XREAD realtime events
  - XRANGE replay on reconnect
  - forward to client
  |
  v
Postgres
  - assistant final message
  - tool_call_log
  - agent_run final status
```

适用:

- 普通 Chat
- 短上下文
- 可控工具链
- 低 TTFT 场景

### 4.2 慢任务 / 批任务

```text
Client POST /chat or /runs
  |
  v
FastAPI
  - create run/task
  - enqueue
  - return run_id
  |
  v
Celery Worker
  - file parsing
  - long RAG
  - slow tools
  - batch analysis
  - agent.run()
  |
  v
Postgres final result
  |
  v
Redis Stream stage events
```

适用:

- 文件分析
- 多分钟任务
- 长 RAG
- 批量任务
- 可重试离线处理

批路径存在 `create run/task -> enqueue` 双写窗口。第一阶段需要增加 PENDING 超时 reaper: 定期扫描超过阈值仍未入队或未启动的 `PENDING/QUEUED` run, 按任务类型重新入队或标记 FAILED, 避免 DB 提交成功但入队失败后永久悬挂。

### 4.3 降级

实时请求在以下情况可降级后台:

- async runner 已满
- provider 限流严重
- 请求触发慢工具
- 文件或长上下文进入离线处理
- 实时路径超出预算

降级后返回 `202 + agent_run_id`, 客户端通过 SSE/WS 或轮询获取结果。

顺序约束:

- 实时路径必须先完成幂等检查和 conversation lock 获取, 再写 user message / agent_run。
- 抢不到 conversation lock 时直接返回 `409 CONVERSATION_BUSY`, 不创建 message/run。
- 内嵌 Runner 使用 `asyncio.create_task` 脱离请求生命周期执行时, 必须在任务启动后写入 `run:{agent_run_id}:lease` 并定期续约; API/Runner 进程崩溃后, reaper 通过 lease 过期判断 RUNNING run 已孤儿化。

---

## 5. 事件协议

事件类型:

```text
RUN_STARTED
PLANNING_STARTED
RETRIEVAL_STARTED
RETRIEVAL_FINISHED
TOOL_CALL_STARTED
TOOL_CALL_FINISHED
LLM_GENERATING
TOKEN
RESULT_COMPOSED
RUN_COMPLETED
ERROR
```

Redis Stream 规则:

- 每个 run 一个 stream, 例如 `stream:run:{agent_run_id}`。
- `XADD` 返回的 stream id 作为事件顺序 id。
- SSE `id` 使用 stream id。
- 客户端重连带 `Last-Event-ID`。
- 服务端先 `XRANGE` 回放, 再 `XREAD BLOCK` 读取实时事件。
- 首个 TOKEN chunk 必须立即 flush, 不等待聚合窗口, 避免人为增加 TTFT。
- 从第二个 TOKEN chunk 起, 按 20-50ms 或 N 个 token 聚合后写入。
- Stream 设置 maxlen 或 TTL; maxlen / TTL 必须覆盖预期最大断线重连和回放窗口, 否则客户端断线超过窗口后 `XRANGE` 会丢事件。
- 每个活跃 SSE 如果独立 `XREAD BLOCK`, 会占用一条 Redis 连接; 容量规划必须覆盖并发 SSE 数、Redis 最大连接数和阻塞读成本。
- 高并发阶段可以引入进程内 fan-out 或多路复用: 单进程少量 Redis 读协程读取 Stream, 再分发给本进程内多个 SSE 连接。

不推荐:

- 只用 Pub/Sub 做事件通道。
- 使用进程内 seq。
- 每 token 一次 Redis 小消息。

---

## 6. 并发、限流与幂等

### 6.1 并发控制

- 单用户 running run 数。
- 单 conversation 串行执行。
- 单 async runner active run 数。
- provider/model 全局并发数。
- 慢工具并发数。

实现:

- Redis lock: `lock:conversation:{conversation_id}`
- Redis semaphore: `semaphore:runner:{runner_group}`
- Redis run lease: `run:{agent_run_id}:lease`
- Redis token bucket: `ratelimit:provider:{provider}:{model}`
- Runner 内部 `asyncio.Semaphore`

Conversation lock 语义:

- 锁 TTL 必须大于 p95 run 时长。
- 长流式 run 必须有 watchdog 续约, 避免锁中途过期后第二个 run 并发写同一段历史。
- run 正常结束、失败或取消时释放锁。
- 抢不到锁的 API 语义需要明确: 第一阶段建议返回 `409 CONVERSATION_BUSY`, 由客户端稍后重试; 若要排队, 必须显式创建排队状态和超时策略。

Runner lease / orphan recovery 语义:

- lease key: `run:{agent_run_id}:lease`, value 至少包含 `runner_id`, `route_type=realtime`, `started_at`, `last_seen_at`。
- Runner 在 run 进入 `RUNNING` 后写 lease, 并按固定间隔续约 TTL。
- lease TTL 必须大于 heartbeat 间隔的 3 倍, 且小于 stuck-run reaper 判定窗口。
- Runner 正常结束、失败或取消时删除 lease。
- Reaper 扫描超时 RUNNING realtime run 时, 如果 lease 不存在或已过期, 标记 run 为 FAILED, 写入 `ERROR` / failed terminal event; 不尝试从中间恢复 Pydantic AI graph。

### 6.2 幂等

- API 支持 `Idempotency-Key`。
- Postgres 加唯一约束 `(user_id, idempotency_key)`。
- assistant message 绑定 `run_id`。
- Worker 重试不得重复写最终答案。

### 6.3 重试

- 实时路径失败快速收敛状态, 可重试或降级后台。
- 后台路径由 Celery 做有限指数退避重试。
- 外部写操作工具默认不自动重试, 除非有业务幂等 key。

---

## 7. 容量与 Cloud 准入指标

第一阶段必须用量化目标判断是否达标:

| 指标 | 第一阶段目标 | 说明 |
| --- | --- | --- |
| 并发实时流 | 3000 路 | 按真实业务目标可调整 |
| TTFT p95 | < 800ms | 首 token 必须立即 flush |
| 单 Runner 进程并发 run | >= 1000 路 | I/O-bound 场景目标, 需压测验证 |
| DB 连接占用 | 流式期间 0 长持有 | DB 连接只用于短事务 |
| Redis Stream lag | 无持续增长 | XADD/XREAD 不形成积压 |
| Provider 429 | 可控且可退避 | 受全局 token bucket 保护 |
| SSE/WS 断线回放 | 100% 按 Last-Event-ID 回放 | 回放源为 Redis Stream |

容量规划必须显式评估:

- Runner 进程数: 按 CPU 核数和单进程 CPU 使用率配置。
- 每进程事件循环负载: token 聚合、JSON、schema 校验、SSE 编码。
- Redis 连接数: active SSE/WS、Runner、API、Worker、锁和限流客户端。
- Redis Stream 内存: event size * events per run * recent active runs。
- DB 连接池: 只服务短事务, 不允许被流式 run 长时间占住。
- Provider 配额: RPM、TPM、并发请求数和退避策略。

---

## 8. 可观测性与度量计划

SLO 必须能被系统直接度量。第一阶段统一接入 Prometheus / OpenTelemetry; 所有指标至少带 `service`、`route`、`runner_id`、`provider`、`model`、`agent_run_id` 或其可聚合标签, 其中高基数字段只进 trace/log, 不直接作为 Prometheus 高基数 label。

### 8.1 SLO 指标采集点

| 指标 | 采集点 | 计算方式 | 告警阈值 |
| --- | --- | --- | --- |
| TTFT p95 | API 受理 `POST /chat` 记录 `chat.accepted_at`; 首个 TOKEN flush 记录 `first_token_flushed_at` | `first_token_flushed_at - accepted_at` 的 p95 | 5 分钟 p95 >= 800ms |
| 并发实时流 | SSE/WS 连接建立和关闭 | `active_sse_connections + active_ws_connections` gauge | 超过容量目标 85% |
| 单 Runner active runs | Runner run start/end | 每个 `runner_id` 的 active run gauge | 超过单进程上限 85% |
| Runner CPU 饱和度 | 进程 CPU + event loop lag | CPU usage、event loop lag p95 | CPU > 80% 或 loop lag p95 > 50ms 持续 5 分钟 |
| DB 连接长持有 | DB pool checkout/checkin hooks | checkout duration histogram; streaming phase active DB connections gauge | streaming phase DB connection > 0 或 checkout p95 超阈值 |
| Redis Stream lag | XADD 最新 id、SSE/reader last delivered id | 每 run 或聚合的 stream lag / unread event count | lag 持续增长 5 分钟或超过回放窗口 50% |
| Redis 连接数 | Redis client pool / Redis INFO clients | connected clients、blocked clients | 超过 Redis maxclients 70% 或 blocked clients 异常增长 |
| Provider 429/5xx | LLM provider response wrapper | rate by provider/model | 429 或 5xx 连续 5 分钟高于预算 |
| Conversation lock wait/reject | lock acquire path | lock wait histogram、409 count | `CONVERSATION_BUSY` 比例异常升高 |
| Run stuck | run 状态扫描 | RUNNING 超过 p99 预算的 run count | > 0 持续 5 分钟 |

### 8.2 日志和 Trace

每个 run 必须贯穿:

- `trace_id`
- `agent_run_id`
- `conversation_id`
- `user_id_hash`
- `runner_id`
- `provider`
- `model`
- `route_type`: `realtime` 或 `batch`
- `first_token_flushed_at`
- `final_status`

Trace 至少覆盖:

- request accepted
- DB read history
- DB connection released before streaming
- agent run started
- first model request
- first token flushed
- Redis Stream XADD
- SSE/WS send
- final DB write

### 8.3 仪表盘

上线前至少具备四张 dashboard:

- API: RPS、错误率、TTFT、SSE/WS active connections、409/429/5xx。
- Runner: active runs、event loop lag、CPU、token flush latency、provider latency。
- Redis: Stream QPS、stream lag、connected clients、blocked clients、memory、evictions。
- Postgres: pool checkout duration、active connections、slow queries、transaction errors。

---

## 9. 模块边界

| 模块 | 职责 |
| --- | --- |
| `app/api` | HTTP/SSE/WS 接入、鉴权、校验、路由 |
| `app/runtime` | Pydantic AI Agent 工厂、编排器、运行依赖 |
| `app/bus` | Redis Stream 事件读写和回放 |
| `app/tasks` | Celery 后台任务入口 |
| `app/db` | Postgres session、repository、状态机 |
| `app/core` | enums、events、schemas、models、ids、config |
| `app/tools` | 工具注册、参数校验、执行和审计 |
| `app/rag` | Embedder、Retriever、VectorStore |

后续需要新增或调整:

- `app/runtime/runner.py`: 实时 async runner。
- `app/bus/stream_bus.py`: Redis Stream event bus。
- `app/api/routers/chat.py`: 按请求类型选择 realtime/batch path。
- `app/api/routers/stream.py`: `Last-Event-ID` 回放。
- `app/tasks`: 拆分 batch/file/rag/tool 队列。

---

## 10. 当前实现需要修正的点

- `run_agent_task` 仍以 Celery 作为 Agent 执行主入口, 需要将实时路径迁移到 async runner。
- `async_bridge` 每任务 `asyncio.run()` 会逐任务创建/销毁事件循环, 不适合高并发实时流式负载。
- RedisEventBus 当前基于 Pub/Sub, 需要演进为 Redis Stream。
- 当前事件 seq 有进程内计数问题, 需要改用 Redis Stream id。
- 需要 token 聚合, 避免每 token 一次 Redis 写。
- 首个 token 必须立即 flush, 后续 token 再聚合。
- 需要保证流式期间不长持有 DB 连接。
- 需要明确 Runner 多进程部署和单进程并发上限。
- 需要评估每 SSE 一个 `XREAD BLOCK` 带来的 Redis 连接模型, 或引入 fan-out。
- conversation lock 需要 TTL、watchdog 续约和抢锁失败语义。
- 需要 conversation/run/stream owner 校验。
- 需要 `Idempotency-Key`。
- 需要 runner lease / heartbeat, 让 reaper 能收敛宿主进程崩溃后的 RUNNING 孤儿 run。
- 需要确保 conversation lock 在创建 user message / run 前获取, 抢锁失败不留下孤儿数据。
- 需要 provider/model 级全局限流。
- 需要 `tool_call_log` 在 Pydantic AI 工具上下文中真实落库。
- `Makefile` 的 worker 队列需要和真实后台任务队列对齐。
- 需要补 Prometheus / OpenTelemetry 埋点, 否则 TTFT、runner 饱和度、Stream lag、DB 连接长持有无法验证。
- 批路径需要 PENDING 超时 reaper, 处理 DB 已提交但入队失败的悬挂 run。

---

## 11. 第一阶段落地顺序

1. 新增实时 async runner 抽象。
2. `POST /chat` 支持实时路径和后台路径分流。
3. Redis Pub/Sub 改 Redis Stream。
4. SSE/WS 支持 `Last-Event-ID` 回放。
5. 首 token 立即 flush, 后续 TOKEN 聚合后写 Stream。
6. 实现 DB 连接短事务模式, 流式期间不持有 DB 连接。
7. Runner 按核数多进程部署, 并配置单进程并发上限。
8. 评估 Redis `XREAD BLOCK` 连接模型, 必要时实现进程内 fan-out。
9. provider/model 级 Redis token bucket。
10. conversation lock + TTL + watchdog + `409 CONVERSATION_BUSY` 语义。
11. runner lease / heartbeat + RUNNING orphan reaper。
12. `Idempotency-Key`。
13. tool call 审计落库。
14. assistant message 绑定 run_id。
15. Celery 队列只保留慢任务/批任务。
16. 补 Prometheus / OpenTelemetry 埋点和 dashboard。
17. 批路径补 PENDING 超时 reaper。
18. 压测 TTFT、active runs、Stream QPS、Redis 连接数、provider 429、runner CPU 饱和度。

---

## 12. 最终边界

```text
FastAPI:
  接入、鉴权、校验、实时入口、SSE/WS 转发

Async Runner:
  常驻事件循环, 承载高并发实时 Agent run

Celery / Worker:
  慢任务、批任务、文件分析、长 RAG、可重试离线任务

Pydantic AI:
  单次 Agent 编排

Postgres:
  权威状态、最终结果、审计

Redis:
  Stream 事件、回放、限流、锁、短状态

Cloud / Gateway:
  网络、安全、扩缩容、可观测性
```
