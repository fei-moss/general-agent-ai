# Agent Execution Platform 架构设计文档

> 异步化的 Agent 执行平台(Async Agent Execution Platform)
> 技术栈:Python 3.10 / FastAPI / SQLAlchemy 2.0 async / Celery 5 + Redis / Postgres / SSE + WebSocket
> 核心约束:零外部依赖即可端到端跑通(MockLLMProvider + HashEmbedder)

---

## 0. 设计目标与核心理念

本平台不是同步 chatbot,而是一个**异步任务执行系统**。用户提交一个请求后,API 层立刻返回 `agent_run_id`(HTTP 202),真正的推理/检索/工具调用在后台 Worker 池中执行,执行过程通过 SSE/WebSocket 以事件流的形式实时推送给客户端。

三条高并发主线索贯穿全文:

| 主线 | 落地手段 |
|------|----------|
| **接入层无状态** | FastAPI 实例不保存任何会话内存态,所有状态落 Postgres / Redis,可任意水平扩容,LB 后随意增删实例 |
| **长任务异步化** | API 只做"鉴权+校验+落库+投递队列",立即返回;执行交给 Celery Worker,响应时间与任务时长解耦 |
| **执行层按任务类型水平扩容** | Worker 按队列分组(`q.intent` / `q.rag` / `q.tool` / `q.llm`),不同类型任务独立扩缩容,互不抢占 |

可运行性是第一公民:**没有任何 API key、不依赖 vLLM/OpenAI,也能完整跑通 demo**。这通过内置 `MockLLMProvider`(流式逐 token echo + 基于 RAG 上下文的模板回答)与 `HashEmbedder`(无依赖确定性向量)实现,真实 provider 通过环境变量切换。

---

## 1. 总体架构

### 1.1 架构图(ASCII)

```
                                   ┌──────────┐
                                   │  Client  │  (Web / SDK / curl)
                                   └────┬─────┘
                          POST /runs    │   ▲  SSE / WebSocket (event stream)
                          (HTTP 202)    │   │
                                   ┌────▼───┴─────────┐
                                   │ API Gateway / LB │  (Nginx / Traefik, 无状态轮询)
                                   └────┬─────────┬───┘
                       ┌────────────────┘         └───────────────┐
                       ▼                                          ▼
        ┌──────────────────────────┐              ┌──────────────────────────┐
        │  FastAPI API 层 (uvicorn)│              │  SSE/WS Gateway (FastAPI) │
        │  - 鉴权 / 限流 / 校验     │              │  - 订阅 Redis Pub/Sub      │
        │  - 生成 conversation_id   │              │    频道 run:{agent_run_id} │
        │    / agent_run_id/trace_id│              │  - 回放历史事件(断线重连) │
        │  - 写 task_state=PENDING  │              │  - 推送 SSE / WS 给客户端  │
        │  - 投递 Celery 队列        │              └──────────────┬────────────┘
        └───────┬──────────┬────────┘                            ▲ subscribe
                │ write     │ enqueue                              │
                ▼           ▼                                      │
        ┌───────────────┐ ┌──────────────────┐    publish events  │
        │   Postgres    │ │  Redis (broker + │◄───────────────────┤
        │ conversation  │ │  result backend +│                    │
        │ message       │ │  event Pub/Sub)  │                    │
        │ agent_run     │ │  (docker :55379) │                    │
        │ task_state    │ └────────┬─────────┘                    │
        │ tool_call_log │          │ consume                       │ publish
        │ (docker:55432)│          ▼                               │
        └───────▲───────┘ ┌────────────────────────────────────┐  │
                │         │   Agent Runtime Worker Pool         │  │
                │ R/W     │   (Celery workers, 按队列分组)       ├──┘
                └─────────┤                                     │
                          │  intent router → planner →          │
                          │  RAG retriever → tool router →      │
                          │  LLM router → result composer       │
                          └──┬──────────┬───────────┬──────────┘
                             │          │           │
                ┌────────────▼──┐  ┌────▼──────┐  ┌─▼────────────────┐
                │ Vector / Search│  │ Tool / MCP│  │  LLM Providers   │
                │ + Cache        │  │ Services  │  │  MockLLMProvider │
                │ numpy 余弦(默认)│  │ (HTTP)   │  │  / OpenAI兼容    │
                │ pgvector(可选) │  │          │  │  / Anthropic/vLLM│
                └────────────────┘  └──────────┘  └──────────────────┘
```

### 1.2 请求生命周期时序图

```
Client      API层        Postgres    Redis(broker)   Worker池       Redis(PubSub)   SSE/WS GW
  │           │              │            │              │               │             │
  │ POST /runs│              │            │              │               │             │
  ├──────────>│              │            │              │               │             │
  │           │ 鉴权/限流/校验 │            │              │               │             │
  │           │ 生成 ids      │            │              │               │             │
  │           ├─INSERT run────>            │              │               │             │
  │           ├─INSERT task_state=PENDING─>│              │               │             │
  │           ├─enqueue(run_id)──────────> │              │               │             │
  │ 202 {run_id}              │            │              │               │             │
  │<──────────┤              │            │              │               │             │
  │           │              │            │── deliver ──> │               │             │
  │ GET /runs/{id}/events (SSE/WS)         │              │               │             │
  ├──────────────────────────────────────────────────────────────────────────────────>│
  │           │              │            │              │               │  SUBSCRIBE  │
  │           │              │            │              │               │<─run:{id}───┤
  │           │              │            │   task_state=RUNNING          │             │
  │           │              │   <────────UPDATE──────────┤               │             │
  │           │              │            │  publish RUN_STARTED──────────>│            │
  │<═══════════════════════════════════════════════════════════════════════ RUN_STARTED│
  │           │              │            │              │   [intent]     │── event ──> │
  │<═══════════════════════════════════════════════════════════════════ INTENT_RESOLVED│
  │           │              │            │              │   [plan]──────>│── event ──> │
  │<══════════════════════════════════════════════════════════════════ PLANNING_STARTED│
  │           │              │            │              │   [rag]───────>│── event ──> │
  │<════════════════════════════════════════════════════════════════ RETRIEVAL_FINISHED│
  │           │              │            │              │   [tool]──────>│── event ──> │
  │<═══════════════════════════════════════════════════════════════ TOOL_CALL_FINISHED │
  │           │              │            │              │   [llm token]─>│── event ──> │
  │<═══════════════════════════════════════════════════════════════════════════ TOKEN ×N│
  │           │              │   <───INSERT message(assistant)            │             │
  │           │              │            │  task_state=DONE              │             │
  │           │              │            │  publish RUN_COMPLETED────────>│            │
  │<═════════════════════════════════════════════════════════════════════ RUN_COMPLETED│
```

---

## 2. 分层与职责

### 2.1 接入层(app/api)

- **无状态**:不缓存会话,所有读写经 Postgres / Redis。
- 职责:鉴权、限流(`RATE_LIMIT_PER_MIN`)、Pydantic 校验、生成 `conversation_id/agent_run_id/trace_id`、落库 `agent_run` 与 `task_state(QUEUED)`、投递 Celery 队列,随后返回 `202 ChatAccepted`。
- 路由(`app/api/routers`):
  - `POST /runs` → 受理并入队,返回 `ChatAccepted`。
  - `GET /runs/{id}` → 返回 `RunStatusOut`。
  - `GET /runs/{id}/events` → SSE 事件流(sse-starlette),订阅 `run:{agent_run_id}`,断线重连按 `Last-Event-ID`(= seq)回放。
  - `WS /runs/{id}/ws` → WebSocket 事件流。
  - `GET /conversations/{id}/messages` → 历史消息。

### 2.2 执行层(app/runtime + app/tasks)

Celery Worker 按队列分组消费,编排管线:

```
intent router → planner → RAG retriever → tool router → LLM router → result composer
```

每一步产生 `AgentEvent` 经 `EventBus.publish("run:{id}", event)` 广播;`seq` 单调递增,`type` 取自 `EventType`。任务状态写 `task_state`,工具调用写 `tool_call_log`,最终助手消息写 `message`,`agent_run.status` 收敛为 `SUCCEEDED/FAILED`。

### 2.3 能力层

- **RAG(app/rag)**:`HashEmbedder`(无依赖确定性向量,维度 `EMBEDDING_DIM`)+ numpy 内存余弦 `VectorStore`(默认),可选 pgvector。
- **Tools(app/tools)**:实现 `Tool` 接口,暴露 `name/description/parameters(JSON Schema)/run(args)`。
- **LLM(app/llm)**:实现 `LLMProvider`,默认 `MockLLMProvider`(流式逐 token echo + 基于检索上下文的模板回答),可切 OpenAI 兼容 / Anthropic(httpx 异步)。

### 2.4 事件总线(app/bus)

基于 `redis.asyncio` Pub/Sub,频道按 `run:{agent_run_id}` 划分。`EventBus.publish/subscribe` 收发 `AgentEvent`。为支持断线回放,事件同时写入 Redis List(`run:{id}:log`)作历史缓冲。

---

## 3. 数据模型

见 `app/core/models.py` 与 `app/db/init.sql`:

| 表 | 关键字段 | 索引 |
|----|----------|------|
| `conversation` | id, user_id, title, created_at, updated_at | PK |
| `message` | id, conversation_id(FK), role, content, token_count, created_at, meta | conversation_id |
| `agent_run` | id, conversation_id(FK), trace_id, status, intent, plan(JSON), error, started_at, finished_at | conversation_id, trace_id |
| `task_state` | id, agent_run_id(FK), task_type, status, attempt, payload(JSON), result(JSON), updated_at | agent_run_id |
| `tool_call_log` | id, agent_run_id(FK), tool_name, arguments(JSON), result(JSON), latency_ms, status, created_at | agent_run_id |

时间列统一 `TIMESTAMPTZ`,JSON 列在 Postgres 落 `JSONB`。

---

## 4. 事件协议

`AgentEvent { event_id, agent_run_id, trace_id, type, seq, ts, data }`,类型见 `EventType`:

`RUN_STARTED → PLANNING_STARTED → INTENT_RESOLVED → RETRIEVAL_STARTED → RETRIEVAL_FINISHED → TOOL_CALL_STARTED → TOOL_CALL_FINISHED → LLM_GENERATING → TOKEN(×N) → RESULT_COMPOSED → RUN_COMPLETED`,任意阶段出错发 `ERROR`。

- SSE:`AgentEvent.to_sse()` 产出 `{event, id(=seq), data(=JSON)}`。
- 序列化:`to_json()/from_json()` 用于 Pub/Sub 收发。

---

## 5. 可运行性与扩展

- **零依赖默认值**:`LLM_PROVIDER=mock`,`HashEmbedder` + numpy 余弦,Mock 工具;无需任何外部 key。
- **水平扩容**:API 实例无状态可任意增减;Worker 按 `q.intent/q.rag/q.tool/q.llm` 独立扩缩容。
- **可观测**:结构化 JSON 日志注入 `trace_id`;`task_state/tool_call_log` 提供执行审计。
- **可替换**:Provider / Embedder / VectorStore / Tool / EventBus 均面向 `app/core/interfaces.py` 协议编程,经工厂按配置选择实现。

---

## 6. 模块边界与契约稳定性

`app/core` 为全平台共享契约层,所有其他模块仅依赖其稳定签名:

- `enums.py`:状态/角色/意图枚举。
- `events.py`:`EventType` + `AgentEvent`。
- `schemas.py`:API 出入参。
- `models.py`:ORM 持久化模型。
- `interfaces.py`:可插拔组件 Protocol。
- `config.py` / `ids.py` / `logging.py`:配置、ID、日志基础设施。

契约一旦发布,后续模块严格遵守;变更需向后兼容或走版本化。
