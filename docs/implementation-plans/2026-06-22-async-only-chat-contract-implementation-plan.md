# 2026-06-22 Async-Only Chat Contract Implementation Plan

## Plan Header

- Specification: `docs/specifications/2026-06-22-async-only-chat-contract-specification.md`
- Spec ID: `SPEC-ASYNC-CHAT-ONLY-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Scope summary: Remove synchronous result waiting from `POST /chat`, reject `stream=false`, and update docs/tests to make streaming async the only Chat contract.
- Out of scope:
  - Removing SSE/WebSocket/status APIs.
  - Removing backend run timeout/reaper protections.
  - Changing realtime vs batch route selection.
  - Formal auth changes.

## Change Steps

### Step 1: Add Async-Only Contract Tests

- Files/modules:
  - `tests/test_chat_routing.py`
- Behavior:
  - Add a test proving `stream=false` returns `422 STREAM_FALSE_NOT_SUPPORTED`.
  - Assert the rejection happens before repository/idempotency/lock/runner side effects.
  - Update direct `create_chat` calls after the route no longer depends on EventBus for sync waiting.
- Verification:
  - `.venv/bin/python -m pytest tests/test_chat_routing.py -q`

### Step 2: Remove Sync Wait From Chat Route

- Files/modules:
  - `app/api/routers/chat.py`
  - `app/api/runner_gateway.py`
- Behavior:
  - Remove `EventBusDep` from `POST /chat`.
  - Remove `_wait_sync` and `await_completion` usage.
  - Add early validation for `stream=false`.
  - Keep accepted response, idempotency, realtime/batch dispatch, locks, and provider preflight unchanged.
- Verification:
  - `.venv/bin/python -m py_compile app/api/routers/chat.py app/api/runner_gateway.py`

### Step 3: Update Documentation

- Files/modules:
  - `docs/INTEGRATION_GUIDE.md`
  - `docs/API.md`
  - `docs/specifications/2026-06-11-high-performance-chat-runtime-specification.md`
- Behavior:
  - Remove synchronous Chat examples and status codes.
  - Document `stream=false` as unsupported.
  - Preserve the async streaming integration flow.
- Verification:
  - `rg -n "stream=false|同步等待|同步模式|504" docs README.md app tests -S`

### Step 4: Release Verification

- Commands:
  - `.venv/bin/python -m pytest tests/test_chat_routing.py tests/test_realtime_runner.py tests/test_stream_replay.py -q`
  - `AI_BOUNDARY_APPROVED=1 make verify-release`
- Evidence:
  - Focused test output.
  - Release summary in `.artifacts/release/summary.json`.
