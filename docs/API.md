# General Agent AI — 前端接口文档

> 版本:0.1.0 ｜ 适用后端:PydanticAI 驱动的 agentic 执行平台
> 本文档面向前端对接,描述全部 HTTP 端点、事件流(SSE / WebSocket)、鉴权、错误码与集成示例。

## 0. 核心模型(必读)

这是一个**异步 Agent 平台**,不是同步问答接口。一次对话的生命周期:

```
Marketplace 前端 ──▶ Marketplace 网关 ──POST /chat──▶ Chat Server
                                             │
                                             └─ 注入可信 account + wallet
                         │
                         ▼
            订阅 SSE / WebSocket 实时事件流
            (RUN_STARTED → 工具调用 → TOKEN 逐字 → RUN_COMPLETED)
```

- 提交后**立即返回**(HTTP 202),默认实时 Chat 的推理(LLM 自主检索 / 调用工具 / 流式生成)由常驻 async RealtimeRunner 执行;慢任务/批任务继续走后台 Worker。
- 前端通过 **SSE 或 WebSocket** 订阅 `agent_run_id` 的事件流,拿到逐 token 输出与工具调用进度。
- 不支持同步等待结果。脚本和前端都必须按 `agent_run_id` 使用事件流、状态接口或会话历史恢复结果。

---

## 1. 通用约定

### Base URL
```
http://localhost:8000        # 本地默认,按部署环境替换
```

### 身份(业务端点必需)

Marketplace 是公开登录态和 JWT 的唯一校验边界。它解析登录用户后,向 Chat Server
的所有业务请求注入:

```http
X-Marketplace-User-ID: marketplace:user:123
X-Marketplace-Wallet: 0x1111111111111111111111111111111111111111
```

规则:

- `X-Marketplace-User-ID` 必须匹配 `marketplace:user:<正整数>`,最长 64 字符。
- `X-Marketplace-Wallet` 必须是 EVM 地址;Chat Server 归一化为小写,并把它作为
  conversation、run、stream、幂等与限流的 owner。
- `POST /chat` 还必须携带与请求头一致的保留 `proxy_payload.marketplace_identity`;
  wallet alias 出现时也必须一致。
- Marketplace 不再生成 URL `user_uuid`,也不把前端 Authorization 原样传给 Chat。
- `/api/v1/chat*` 不是本项目的接口契约。

所有环境都只接受上述专用头,不存在身份模式开关。生产部署在批准的私有网络内,
按当前设计不需要内部服务凭证、签名或应用层加密。

#### 开发调试

开发环境直接调试 Chat Server 时也必须手动注入上述两个 Marketplace 专用头。
URL `user_uuid`、普通 Bearer、`X-API-Key` 和 WebSocket query token 都不能作为
用户侧 Chat 身份。

> 公开开发地址上的 plain Marketplace headers 不构成密码学证明,不得当成生产安全边界。
> `/rag/*` 的内部管理员 Bearer/API-key 契约独立于用户侧 Chat 身份,不受本次调整影响。

豁免鉴权的公开路径:`/healthz`、`/readyz`、`/docs`、`/redoc`、`/openapi.json`。

### Trace ID
- 每个响应都会回写头 `X-Trace-Id`,用于排查问题,建议前端日志记录。
- 可在请求头主动传 `X-Trace-Id` 透传(不传则后端生成)。

### CORS
后端开启宽松 CORS(`allow_origins: *`),前端可跨域直连(生产会收敛)。
浏览器 `OPTIONS` preflight 会在鉴权前由 CORS 中间件处理。生产前端只调用
Marketplace;Marketplace 到 Chat 的代理请求携带专用身份头。

### 限流
仅对 `POST /chat` 限流(按可信 wallet owner 滑动窗口,
默认 **60 次/分钟**)。超限返回 **429**:
```
HTTP 429
Retry-After: <秒>
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
```
正常响应也会带 `X-RateLimit-Limit` / `X-RateLimit-Remaining`。

### 统一错误体
```json
{ "detail": "错误说明" }
```

| 状态码 | 含义 |
|--------|------|
| 401 | 缺少/无效身份凭证 |
| 403 | 无权访问该资源(会话归属不符) |
| 404 | 资源不存在 |
| 422 | 请求体或 Marketplace header/body 身份校验失败 |
| 429 | 触发限流 |
| 503 | 任务队列 / 依赖未就绪 |

---

## 2. 端点总览

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/chat` | Marketplace 提交一次对话(核心) | Marketplace 专用头 + reserved payload |
| GET  | `/runs/{agent_run_id}` | Marketplace 查询运行状态 | Marketplace 专用头 |
| GET  | `/stream/{agent_run_id}` | Marketplace SSE 事件流 | Marketplace 专用头 |
| WS   | `/ws/{agent_run_id}` | Marketplace WebSocket 事件流 | Marketplace 专用头 |
| POST | `/conversations` | 创建会话 | ✅ |
| GET  | `/conversations/{id}` | 会话详情(含消息) | ✅ |
| GET  | `/conversations` | 会话列表(分页) | ✅ |
| GET  | `/healthz` `/readyz` | 健康检查 | ❌ |

> *SSE 鉴权对浏览器有坑,见 [§5.3](#53-浏览器集成注意鉴权与-sse)。

---

## 3. 对话接口

### 3.1 POST /chat — Marketplace 提交对话(核心)

**URL**:`/chat`

**请求头**:

```http
Content-Type: application/json
X-Marketplace-User-ID: marketplace:user:123
X-Marketplace-Wallet: 0x1111111111111111111111111111111111111111
```

**请求体** `ChatRequest`:

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `message` | string | ✅ | — | 用户消息(非空) |
| `conversation_id` | string \| null | ❌ | null | 续接已有会话;不传则**自动新建** |
| `stream` | boolean | ❌ | `true` | 兼容字段;省略或传 `true`;`false` 会返回 422 |
| `metadata` | object | ❌ | `{}` | 透传元数据;`agent_context` / `current_agent_address` 会归一化为当前 Agent 运行上下文 |
| `proxy_payload` | object | ✅* | `{}` | Marketplace 注入的运行上下文;Marketplace flow 必须含 reserved identity |

```json
{
  "message": "帮我算一下 (123+456)*7 等于多少",
  "conversation_id": null,
  "stream": true,
  "proxy_payload": {
    "marketplace_identity": {
      "user_id": "marketplace:user:123",
      "wallet_address": "0x1111111111111111111111111111111111111111"
    },
    "user_address": "0x1111111111111111111111111111111111111111",
    "wallet_address": "0x1111111111111111111111111111111111111111"
  }
}
```

`marketplace_identity` 是 Marketplace 独占写入的保留命名空间。缺失或畸形返回
`422 MARKETPLACE_IDENTITY_INVALID`;与专用头或 wallet alias 冲突返回
`422 MARKETPLACE_IDENTITY_MISMATCH`。前端无需新增这些字段,由 Marketplace 网关覆盖注入。

当前 Agent 页面接入示例:

```json
{
  "message": "这个 Agent 支持哪条链？24 小时交易量是多少？",
  "stream": true,
  "metadata": {
    "agent_context": {
      "agent_address": "0x17B09FC949f031dbD540D4caDE59805A08Ee5043",
      "contract_address": "0x17B09FC949f031dbD540D4caDE59805A08Ee5043",
      "agent_id": "#1053",
      "protocol": "Agent"
    },
    "current_agent_address": "0x17B09FC949f031dbD540D4caDE59805A08Ee5043",
    "page_context": "agent_detail",
    "mode": "realtime",
    "task_type": "chat"
  }
}
```

当前 Agent 地址从 `metadata.current_agent_address` / `metadata.agent_context` 派生,不需要放进
`proxy_payload`。请求体里不要传 `run_context`;传入时会返回 422。
调用方提供的 URL `user_uuid`、普通 Authorization 或 API key 不参与 Chat owner 解析。

#### 响应: **202 Accepted**(`ChatAccepted`)

```json
{
  "conversation_id": "conv_xxx",
  "agent_run_id": "run_xxx",
  "trace_id": "trace_xxx",
  "status": "PENDING",
  "stream_url": "/stream/run_xxx",
  "ws_url": "/ws/run_xxx"
}
```
> 拿到 `agent_run_id` 后,立刻用 `stream_url` 订阅 SSE,或 `ws_url` 连 WebSocket。

#### 不支持 `stream:false`

`POST /chat` 永远是异步受理接口。传
`stream:false` 会返回 **422**:

```json
{ "detail": "STREAM_FALSE_NOT_SUPPORTED" }
```

脚本场景如果不想渲染逐 token，也应该订阅到 `RUN_COMPLETED`，或轮询
携带同一组 Marketplace 专用头调用 `GET /runs/{agent_run_id}` 后读取
`GET /conversations/{conversation_id}` 的消息历史。

---

## 4. 事件流(SSE / WebSocket)

两种通道**推送完全相同的事件对象**,任选其一。每条事件为一个 `AgentEvent`:

```jsonc
{
  "event_id": "evt_xxx",
  "agent_run_id": "run_xxx",
  "trace_id": "trace_xxx",
  "type": "TOKEN",          // 事件类型,见下表
  "seq": 9,                  // 同一 run 内单调递增,用于排序/去重
  "ts": 1780903390.12,       // unix 秒(float)
  "data": { "token": "向量" } // 载荷,结构随 type 而定
}
```

### 4.1 事件类型与 data 载荷

| `type` | 触发时机 | `data` 字段 | 前端处理建议 |
|--------|----------|-------------|--------------|
| `RUN_STARTED` | 运行开始 | `{ message }` | 显示"思考中" |
| `PLANNING_STARTED` | 进入 agentic loop | `{}` | — |
| `RETRIEVAL_STARTED` | LLM 自主发起知识检索 | `{ query }` | 显示"检索资料…" |
| `RETRIEVAL_FINISHED` | 检索完成 | `{}` | — |
| `TOOL_CALL_STARTED` | LLM 自主调用工具 | `{ tool_name }` | 显示"调用 {tool}…" |
| `TOOL_CALL_FINISHED` | 工具返回 | `{ tool_name }` | — |
| `LLM_GENERATING` | 开始生成最终回答 | `{}` | 准备打字机 |
| **`TOKEN`** | **逐 token 输出** | `{ token }` | **拼接 token 渲染** |
| `RESULT_COMPOSED` | 回答生成完毕 | `{ length }` | — |
| **`RUN_COMPLETED`** | **运行结束(终止事件)** | `{ status, content? }` | **结束流;读 content** |
| `ERROR` | 某阶段出错(终止事件) | `{ stage, error }` | 提示错误 |

**关键规则**:
- **拼接答案** = 把所有 `TOKEN` 事件的 `data.token` 按 `seq` 顺序连起来。
- **何时结束** = 收到 `RUN_COMPLETED` 或 `ERROR` 即终止(两者都是终止事件,流随后关闭)。
- `RUN_COMPLETED` 成功时 `data = { status: "SUCCEEDED", content: "<完整答案>" }`;失败时 `data = { status: "FAILED" }`(无 content)。可用 `content` 兜底校验你拼的 TOKEN 是否完整。
- 工具调用可能发生**多次**(LLM 自主决定),前端按 START/FINISHED 成对展示进度即可。

> 📌 **agentic 改造说明**:旧的 `INTENT_RESOLVED` 事件已不再产生(意图识别被 LLM 自主推理取代);`/runs` 与运行对象里的 `intent` 字段恒为 `null`,保留仅为兼容,前端可忽略。

### 4.2 SSE:GET /stream/{agent_run_id}

标准 `text/event-stream`,每条:
```
event: TOKEN
id: 9
data: {"event_id":"evt_x","agent_run_id":"run_x","type":"TOKEN","seq":9,"ts":1780903390.1,"data":{"token":"向量"}}
```
- `event` = 事件类型,`id` = seq,`data` = 完整 `AgentEvent` JSON 字符串(需 `JSON.parse`)。
- 服务端在 `RUN_COMPLETED`/`ERROR` 后主动关闭连接。

### 4.3 WebSocket:WS /ws/{agent_run_id}

- 每帧是一条 `AgentEvent` 的 **JSON 字符串**(注意:**不带** SSE 的 `event:`/`id:` 包装,直接 `JSON.parse(frame)`)。
- 收到终止事件后服务端关闭连接。
- **Marketplace 鉴权**:Marketplace 的 WebSocket 代理在握手时注入两项专用头。
- 浏览器 WebSocket 不能设置这些内部头,因此必须通过 Marketplace 的 WebSocket 代理。

---

## 5. Marketplace 代理集成示例

前端接口不变:浏览器只携带 Marketplace 登录态调用 Marketplace,不会直接构造
Chat Server 身份字段。以下代码表示 Marketplace 服务端到 Chat Server 的内部调用。

### 5.1 提交 + SSE

浏览器原生 `EventSource` **无法设置请求头**,而 `/stream` 需要鉴权头,故推荐用 [`@microsoft/fetch-event-source`](https://www.npmjs.com/package/@microsoft/fetch-event-source):

```ts
import { fetchEventSource } from '@microsoft/fetch-event-source';

const BASE = 'http://localhost:8000';
const MARKETPLACE_HEADERS = {
  'X-Marketplace-User-ID': 'marketplace:user:123',
  'X-Marketplace-Wallet': '0x1111111111111111111111111111111111111111',
};

// 1) 提交对话
const res = await fetch(`${BASE}/chat`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', ...MARKETPLACE_HEADERS },
  body: JSON.stringify({
    message: '帮我算一下 (123+456)*7',
    stream: true,
    proxy_payload: {
      marketplace_identity: {
        user_id: 'marketplace:user:123',
        wallet_address: '0x1111111111111111111111111111111111111111',
      },
      user_address: '0x1111111111111111111111111111111111111111',
      wallet_address: '0x1111111111111111111111111111111111111111',
    },
  }),
});
const { agent_run_id, stream_url } = await res.json();

// 2) 订阅事件流,拼接 TOKEN
let answer = '';
await fetchEventSource(`${BASE}${stream_url}`, {
  headers: MARKETPLACE_HEADERS,
  onmessage(ev) {
    const evt = JSON.parse(ev.data);            // AgentEvent
    switch (evt.type) {
      case 'TOOL_CALL_STARTED':
        console.log('调用工具', evt.data.tool_name); break;
      case 'TOKEN':
        answer += evt.data.token;                // 逐字渲染
        render(answer); break;
      case 'RUN_COMPLETED':
        console.log('完成', evt.data.status, evt.data.content); break;
      case 'ERROR':
        console.error('出错', evt.data.error); break;
    }
  },
});
```

### 5.2 WebSocket

```ts
// Marketplace 的服务端 WebSocket 代理负责向握手注入 MARKETPLACE_HEADERS。
const ws = marketplaceWebSocketProxy(`/ws/${agent_run_id}`, MARKETPLACE_HEADERS);
let answer = '';
ws.onmessage = (e) => {
  const evt = JSON.parse(e.data);               // 直接是 AgentEvent
  if (evt.type === 'TOKEN') { answer += evt.data.token; render(answer); }
  if (evt.type === 'RUN_COMPLETED' || evt.type === 'ERROR') ws.close();
};
```

### 5.3 浏览器集成注意:鉴权与 SSE

| 通道 | 浏览器能否设鉴权 | 方案 |
|------|------------------|------|
| 原生 `EventSource` | 不能设自定义 header | 由 Marketplace 代理 SSE 并注入专用头 |
| WebSocket | 浏览器不能设自定义 header | 由 Marketplace 代理握手并注入专用头 |
| `fetch`(普通 REST) | 可以 | Marketplace 服务端注入专用头;前端不注入 |

开发直连同样需要注入两个 Marketplace 专用头,没有 `user_uuid`/query-token 回退。

---

## 6. 会话与状态接口

### 6.1 POST /conversations — 创建会话(201)
请求 `{ "title": "可选标题" }` → 返回 `ConversationOut`:
```json
{ "id": "conv_xxx", "user_id": "demo-user-1", "title": "可选标题",
  "created_at": "2026-06-08T10:00:00Z", "updated_at": "2026-06-08T10:00:00Z" }
```
> 不必先建会话:`POST /chat` 不传 `conversation_id` 会自动创建。

### 6.2 GET /conversations/{id} — 会话详情(含消息)
返回 `ConversationDetailOut`(在 `ConversationOut` 基础上加 `messages`):
```json
{
  "id": "conv_xxx", "user_id": "demo-user-1", "title": null,
  "created_at": "...", "updated_at": "...",
  "messages": [
    { "id": "msg_1", "conversation_id": "conv_xxx", "role": "USER",
      "content": "帮我算一下 (123+456)*7", "token_count": 12,
      "created_at": "...", "meta": {} },
    { "id": "msg_2", "conversation_id": "conv_xxx", "role": "ASSISTANT",
      "content": "（123+456）×7 的结果是 4053。", "token_count": 18,
      "created_at": "...", "meta": {} }
  ]
}
```
> 访问非本人会话返回 403;不存在返回 404。

### 6.3 GET /conversations — 会话列表(分页)
Query:`limit`(1–100,默认 20)、`offset`(默认 0)。返回 `ConversationOut[]`(当前用户的会话)。

### 6.4 GET /runs/{agent_run_id} — 运行状态(轮询用)
返回 `RunStatusOut`:
```json
{ "agent_run_id": "run_xxx", "status": "SUCCEEDED", "intent": null, "error": null }
```
> 适合不走事件流时轮询状态;`intent` 恒为 `null`(见 §4.1 说明)。

### 6.5 GET /healthz · /readyz — 健康检查(公开)
存活/就绪探针,无需鉴权,返回 200 表示正常。

---

## 7. 枚举附录

**RunStatus**(运行状态):`PENDING` · `RUNNING` · `SUCCEEDED` · `FAILED` · `CANCELLED`
**MessageRole**(消息角色):`USER` · `ASSISTANT` · `SYSTEM` · `TOOL`
**EventType**(事件类型):见 [§4.1](#41-事件类型与-data-载荷)

---

## 8. 典型前端流程小结

```
1. (可选) POST /conversations            → 拿 conversation_id(或直接跳过)
2. POST /chat { message, stream:true }   → 拿 agent_run_id + stream_url
3. 订阅 SSE(fetch-event-source)/ WS     → 拼 TOKEN、展示工具进度
4. 收到 RUN_COMPLETED                     → 渲染最终答案(data.content)
5. (可选) GET /conversations/{id}         → 回显历史消息
```

后端默认 `LLM_PROVIDER=mock`(零 key 可跑通);切换 claude / openai / qwen / gemini 对前端**完全透明**,接口与事件流不变。
