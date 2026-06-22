# General Agent AI Chat Server Integration Guide

This guide is the external contract for humans and Agents integrating with the
Chat Server. It describes the currently deployed API shape, not future auth or
tenant-management plans.

## Base URL

Use the environment URL provided by operations. Current DockerHost smoke URL:

```text
https://api-chris-general-agent-ai-chat-prod.dkhost.vixmk-yo.org
```

Treat DockerHost URLs as test/staging endpoints unless operations promotes one
as stable.

## Identity Header

Current identity is header-derived:

```http
Authorization: Bearer <user_id>
```

or:

```http
X-API-Key: <user_id>
```

The value is treated as `user_id` and stored on owned resources such as
conversations, runs, and knowledge bases. This is not formal authentication; it
is an upstream-auth identity pass-through placeholder. Use a stable internal
user id, for example `alice.internal`, and reuse the same value for follow-up
requests.

Public endpoints:

- `GET /healthz`
- `GET /readyz`
- `GET /metrics`
- `/docs`, `/redoc`, `/openapi.json`

All business endpoints require an identity header.

## Chat

### Start A Realtime Chat

```bash
curl -sS -X POST "$BASE_URL/chat" \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer alice.internal' \
  -H 'Idempotency-Key: chat-001' \
  -d '{
    "message": "请用三句话介绍一下这个系统现在的能力。",
    "stream": true,
    "metadata": {
      "mode": "realtime",
      "task_type": "chat"
    }
  }'
```

Request body:

```json
{
  "conversation_id": "optional existing conversation id",
  "message": "required non-empty user message",
  "stream": true,
  "metadata": {
    "mode": "auto | realtime | batch",
    "task_type": "chat | file_analysis | slow_tool | batch",
    "knowledge_base_id": "optional kb id"
  }
}
```

Response is HTTP `202`:

```json
{
  "conversation_id": "conv_xxx",
  "agent_run_id": "run_xxx",
  "trace_id": "trace_xxx",
  "status": "PENDING",
  "stream_url": "/stream/run_xxx",
  "ws_url": "/ws/run_xxx",
  "route_type": "realtime"
}
```

Use `Idempotency-Key` for client retries. Reusing the same key with the same
payload returns the original run; reusing it with a different payload returns
`409 IDEMPOTENCY_CONFLICT`.

### Continue A Conversation

Pass the previous `conversation_id`:

```json
{
  "conversation_id": "conv_xxx",
  "message": "基于上一轮回答，再展开讲一下 RAG 链路。",
  "stream": true,
  "metadata": {"mode": "realtime"}
}
```

Same-conversation realtime work is serialized. If another realtime run is active
for that conversation, the API returns `409 CONVERSATION_BUSY`.

### Synchronous Result

For simple scripts that do not want SSE:

```bash
curl -sS -X POST "$BASE_URL/chat" \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer alice.internal' \
  -d '{
    "message": "GLM-5.2 是否已经接通？",
    "stream": false,
    "metadata": {"mode": "realtime"}
  }'
```

This waits for a terminal event. Use streaming for normal interactive clients
and longer tasks.

## Streaming

### SSE

```bash
curl -N "$BASE_URL/stream/run_xxx" \
  -H 'Authorization: Bearer alice.internal'
```

The server emits standard SSE frames:

```text
id: 1782112292712-0
event: TOKEN
data: {"event_id":"evt_xxx","agent_run_id":"run_xxx","trace_id":"trace_xxx","type":"TOKEN","stream_id":"1782112292712-0","seq":6,"ts":1782112292.7,"data":{"token":"hello"}}
```

Important event types:

- `RUN_STARTED`
- `PLANNING_STARTED`
- `RETRIEVAL_STARTED`
- `RETRIEVAL_FINISHED`
- `TOOL_CALL_STARTED`
- `TOOL_CALL_FINISHED`
- `LLM_GENERATING`
- `TOKEN`
- `RESULT_COMPOSED`
- `RUN_COMPLETED`
- `ERROR`

Read answer deltas from:

```json
{"data": {"token": "text chunk"}}
```

Terminal success:

```json
{
  "type": "RUN_COMPLETED",
  "data": {
    "status": "SUCCEEDED",
    "content": "full final answer"
  }
}
```

Terminal failure:

```json
{
  "type": "ERROR",
  "data": {
    "stage": "provider_rate_limit | runner | stream_replay | agent",
    "error": "machine-readable error"
  }
}
```

SSE `id` is a Redis Stream id. Store the last seen id and reconnect with:

```http
Last-Event-ID: <last_sse_id>
```

If the cursor is older than retained stream entries, the server returns an
`ERROR` event with `data.error = "STREAM_GAP"`. In that case, query run status
and conversation history instead of trying to replay old tokens.

### WebSocket

```text
ws(s)://<host>/ws/run_xxx?token=alice.internal
```

or pass `Authorization: Bearer <user_id>` during the WebSocket handshake. Use
`last_event_id=<stream_id>` to resume from a cursor.

## Run Status

```bash
curl -sS "$BASE_URL/runs/run_xxx" \
  -H 'Authorization: Bearer alice.internal'
```

Response:

```json
{
  "agent_run_id": "run_xxx",
  "status": "PENDING | RUNNING | SUCCEEDED | FAILED | CANCELLED",
  "intent": null,
  "error": null
}
```

## Conversations

Create an empty conversation:

```bash
curl -sS -X POST "$BASE_URL/conversations" \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer alice.internal' \
  -d '{"title": "Support analysis"}'
```

List conversations:

```bash
curl -sS "$BASE_URL/conversations?limit=20&offset=0" \
  -H 'Authorization: Bearer alice.internal'
```

Get one conversation with messages:

```bash
curl -sS "$BASE_URL/conversations/conv_xxx" \
  -H 'Authorization: Bearer alice.internal'
```

## RAG Knowledge Bases

### Create Knowledge Base

```bash
curl -sS -X POST "$BASE_URL/rag/knowledge-bases" \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer alice.internal' \
  -d '{
    "name": "Product docs",
    "description": "Internal product support knowledge"
  }'
```

### Import Text Document

```bash
curl -sS -X POST "$BASE_URL/rag/documents" \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer alice.internal' \
  -d '{
    "knowledge_base_id": "kb_xxx",
    "title": "DockerHost notes",
    "content": "DockerHost runs the API, worker, reaper, Postgres, Redis, and pgvector.",
    "source_type": "api",
    "metadata": {"source": "integration-guide"}
  }'
```

Response:

```json
{
  "document_id": "doc_xxx",
  "job_id": "ragjob_xxx",
  "status": "PENDING",
  "replayed": false
}
```

Poll ingestion:

```bash
curl -sS "$BASE_URL/rag/ingestion-jobs/ragjob_xxx" \
  -H 'Authorization: Bearer alice.internal'
```

Wait for `status = "SUCCEEDED"` and document `status = "EMBEDDED"`.

### Query Knowledge Base Directly

```bash
curl -sS -X POST "$BASE_URL/rag/query" \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer alice.internal' \
  -d '{
    "knowledge_base_id": "kb_xxx",
    "query": "DockerHost 部署里有哪些服务？",
    "top_k": 3,
    "strict": false
  }'
```

Response includes:

```json
{
  "chunks": [
    {
      "chunk_id": "chunk_xxx",
      "document_id": "doc_xxx",
      "knowledge_base_id": "kb_xxx",
      "content": "matched text",
      "score": 0.83,
      "citation": {"chunk_index": 0},
      "metadata": {}
    }
  ],
  "degraded": false,
  "reason": null,
  "latency_ms": 120,
  "query_id": "optional"
}
```

### Chat With RAG

Pass `knowledge_base_id` inside chat metadata:

```json
{
  "message": "基于知识库回答：DockerHost 部署里有哪些服务？",
  "stream": true,
  "metadata": {
    "mode": "realtime",
    "knowledge_base_id": "kb_xxx"
  }
}
```

The Agent decides whether to call the knowledge-search tool during the run.

## Health And Operations

```bash
curl -sS "$BASE_URL/healthz"
curl -sS "$BASE_URL/readyz"
curl -sS "$BASE_URL/metrics"
```

`/healthz` only proves the API process is alive.

`/readyz` checks:

- `db`
- `redis`
- `event_bus`
- `provider_secret`
- `provider_limiter`
- `reaper`

For real model traffic, `provider_secret` should be `configured`.

`/metrics` returns Prometheus text. Useful metrics include:

- `chat_ttft_seconds_*`
- `provider_rate_limit_decisions_total`
- `provider_rate_limit_tokens_reserved_total`
- `provider_rate_limit_tokens_settled_total`
- `redis_stream_events_total`
- `runner_active_runs`
- `runner_timeouts_total`
- `reaper_runs_total`

## Error Reference

Common HTTP responses:

- `401`: missing identity header.
- `403`: resource belongs to another `user_id`.
- `404`: run, conversation, knowledge base, document, or job not found.
- `409`: conversation busy, disabled knowledge base, or idempotency conflict.
- `422`: invalid request body, usually empty required fields.
- `429`: user or provider rate limit.
- `503`: queue, limiter, Redis, or provider guardrail unavailable.
- `504`: synchronous wait timed out.

Common machine-readable details:

- `CONVERSATION_BUSY`
- `IDEMPOTENCY_CONFLICT`
- `PROVIDER_LIMITER_UNAVAILABLE`
- `RAG_QUEUE_UNAVAILABLE`
- `KNOWLEDGE_BASE_DISABLED`
- `STREAM_GAP`
- `RUN_TIMEOUT`

## Agent Integration Checklist

1. Set `BASE_URL`.
2. Pick a stable `user_id` and send `Authorization: Bearer <user_id>`.
3. Use `Idempotency-Key` on every retryable `POST /chat`.
4. Submit `POST /chat` with `stream=true`.
5. Subscribe to `stream_url` with the same identity header.
6. Accumulate `TOKEN.data.token` until `RUN_COMPLETED`.
7. Persist last SSE `id`; reconnect with `Last-Event-ID`.
8. On `STREAM_GAP`, call `/runs/{id}` and `/conversations/{id}`.
9. For RAG, create a KB, import documents, wait for `SUCCEEDED`, then pass `knowledge_base_id` in chat metadata.
10. Treat `/readyz` as the traffic gate and `/metrics` as the observability surface.
