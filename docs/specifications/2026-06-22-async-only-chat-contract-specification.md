# 2026-06-22 Async-Only Chat Contract Specification

## Context

- Spec ID: `SPEC-ASYNC-CHAT-ONLY-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Related specification: `SPEC-CHAT-RUNTIME-001`
- Related implementation plan: `docs/implementation-plans/2026-06-22-async-only-chat-contract-implementation-plan.md`
- Source request:
  - Remove synchronous Chat result waiting.
  - First official Chat Server release should expose only async accepted runs plus SSE/WebSocket streaming.
  - Synchronous HTTP waits are poor UX and create avoidable API worker pressure under load.

## Problem

`POST /chat` currently accepts `stream=false` and then keeps the HTTP request open while waiting for terminal run events. That duplicates the event stream contract, ties up request capacity, and encourages clients to use the service like a synchronous Q&A endpoint.

## Product Semantics

- `POST /chat` is an async submission endpoint only.
- Successful accepted requests always return HTTP `202` with `conversation_id`, `agent_run_id`, `trace_id`, `stream_url`, `ws_url`, and `route_type`.
- Clients must obtain output through:
  - `GET /stream/{agent_run_id}` SSE;
  - `WS /ws/{agent_run_id}`;
  - `GET /runs/{agent_run_id}` and `GET /conversations/{conversation_id}` for state/history recovery.
- `stream` may be omitted or set to `true` for compatibility with existing request bodies.
- `stream=false` is no longer supported and must be rejected before creating conversation messages, runs, tasks, locks, or idempotency records.
- Backend run timeouts, reaper behavior, stream replay, and run status polling remain in scope; only synchronous HTTP result waiting is removed.

## API Contract

- Request:
  - `message`: required non-empty string.
  - `conversation_id`: optional existing conversation id.
  - `stream`: optional boolean; only omitted or `true` is accepted.
  - `metadata`: optional object.
- Response:
  - HTTP `202` `ChatAccepted` for accepted runs.
- Error:
  - `stream=false` returns HTTP `422`.
  - Error detail: `STREAM_FALSE_NOT_SUPPORTED`.
- Removed behavior:
  - No `200` synchronous answer response from `POST /chat`.
  - No `502` synchronous-run failure response from `POST /chat`.
  - No `504` synchronous wait timeout from `POST /chat`.
  - API no longer subscribes to the EventBus from the Chat route to await completion.

## Performance And Reliability Requirements

- API request lifetime must cover validation, ownership/idempotency checks, run creation, enqueue/realtime dispatch, and response only.
- API request lifetime must not include LLM generation, tool execution, RAG retrieval during Agent execution, or waiting for terminal events.
- Removing sync waiting must not weaken:
  - conversation owner checks;
  - idempotency replay;
  - realtime capacity/conversation locks;
  - provider preflight;
  - stream replay;
  - run timeout/reaper convergence.

## Compatibility

- Existing clients sending `stream=true` continue to work.
- Existing clients omitting `stream` continue to work because the default remains `true`.
- Clients using `stream=false` must migrate to SSE/WebSocket or status/history polling.
- `ChatRequest.stream` remains present for short-term request-shape compatibility, but only `true` is accepted.

## Acceptance Criteria

- `POST /chat` with `stream=false` returns `422 STREAM_FALSE_NOT_SUPPORTED`.
- The rejection happens before repository, lock, runner, queue, or idempotency side effects.
- `POST /chat` no longer imports or calls synchronous completion waiting.
- Focused tests prove async-only behavior and existing accepted/idempotency behavior.
- Integration docs and API docs no longer describe synchronous Chat as supported.
- `make verify-release` passes.
