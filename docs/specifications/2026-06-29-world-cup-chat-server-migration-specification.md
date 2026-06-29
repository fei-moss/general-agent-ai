# 2026-06-29 World Cup Chat Server Migration Specification

- Spec ID: `SPEC-WORLDCUP-CHAT-SERVER-MIGRATION-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`

## Context

- PRD/source request: create a new sibling project for a World Cup match forecasting Chat Server, migrate the reusable async Chat Server architecture, and verify it through Harness plus DockerHost live smoke.
- Target baseline: `/Users/chris/AiProject/general-agent-ai` copied into `/Users/chris/AiProject/world-cup-chat-server` as the platform baseline.
- Current behavior: source project is a generic async Agent execution platform whose default behavior policy was tuned for Ask this Agent / trading Agent detail pages and MOSS RAG evaluation.
- Problem: a copied repository would preserve the platform but also preserve wrong business semantics, test fixtures, DockerHost names, and project docs.
- Non-goals: no real-money order placement, no live Polymarket execution integration, no full World Cup market-data crawler in this migration pass, and no production guarantee from a single smoke test.

## Product Semantics

- User/operator workflow:
  - Users call `POST /chat` with a World Cup match or slate question.
  - API returns `202` with `agent_run_id`, `conversation_id`, `stream_url`, and `ws_url`.
  - Clients subscribe to SSE or WebSocket and recover through run status or conversation history.
- State model:
  - Preserve `conversation`, `message`, `agent_run`, `task_state`, `idempotency_record`, RAG, and tool-call audit tables.
  - Preserve Redis Stream replay and runner/reaper leases.
- Ownership and identity rules:
  - Preserve header-derived `user_id` placeholder semantics until a real upstream auth service is introduced.
  - Do not expose private wallet, Polymarket account, order, position, or secret data through default behavior.
- Permissions/authentication:
  - Preserve existing business endpoint auth behavior and RAG admin whitelist behavior.
- Empty, error, retry, timeout, duplicate, and partial-failure behavior:
  - Preserve async-only chat, `stream:false` rejection, idempotency key handling, conversation lock, provider limiter fail-closed behavior, timeout terminal events, and pending-run reaper.
- Compatibility and migration expectations:
  - API/stream/db architecture remains compatible with the source platform.
  - Default Agent identity, golden cases, docs, DockerHost names, and seed knowledge must be World Cup-specific.
  - MOSS and Ask this Agent artifacts are not migrated as active product assets.

## API / Interface Contract

- Routes, commands, events, jobs, or UI surfaces:
  - Preserve `/chat`, `/stream/{agent_run_id}`, `/ws/{agent_run_id}`, `/runs/{agent_run_id}`, `/conversations`, `/rag/*`, `/healthz`, `/readyz`, and `/metrics`.
- Request fields and validation:
  - Preserve `ChatRequest` fields: `message`, `conversation_id`, `stream`, `metadata`.
  - Preserve async-only validation: `stream=false` returns `STREAM_FALSE_NOT_SUPPORTED`.
- Response/envelope fields and types:
  - Preserve `ChatAccepted` fields and route type.
  - Preserve `AgentEvent` event types and terminal semantics.
- Status/error codes:
  - Preserve 401/403/404/409/422/429/503 behavior.
- Backward compatibility:
  - Existing frontend integration contract remains valid, but user-facing docs and examples must reference World Cup forecasting.

## Data / Schema / Projection Impact

- Tables, indexes, migrations, backfills:
  - No schema migration is required for this pass.
- Read models, projections, snapshots, caches:
  - No projection changes.
- Historical data behavior:
  - New project starts with its own database; no source data migration is required.
- Performance-sensitive queries or write paths:
  - Preserve source platform limits: no long DB connection during streaming, Redis Stream replay, provider token bucket, and reaper convergence.

## Architecture

- Modules/files expected to change:
  - `app/runtime/chat_behavior.py`: World Cup forecasting identity, answer principles, and refusal boundaries.
  - `app/runtime/agent_factory.py`: mock answer text for World Cup smoke.
  - `tests/chat_eval/*` and behavior tests: World Cup golden cases.
  - `scripts/sample_knowledge.json`: minimal World Cup seed knowledge.
  - `AGENTS.md`, `README.md`, API/integration docs, DockerHost template/runbook, app title.
- Data flow:
  - Same as source: FastAPI -> RealtimeRunner/Celery -> Pydantic AI -> tools/RAG -> Redis Stream -> SSE/WS -> Postgres final state.
- Transaction/concurrency boundaries:
  - Preserve source boundaries.
- Observability/logging/metrics:
  - Preserve `/metrics`, trace id, run id, provider/model metrics, reaper metrics, and DockerHost release audit.
- Rollback strategy:
  - Since this is a new repository, rollback means redeploying a previously verified Git ref or deleting the DockerHost environment.

## Harness Classification

- Expected gate(s):
  - `HARNESS-SPEC-FIRST-FEATURE` for migration and runtime behavior changes.
  - `HARNESS-FOCUSED-CHANGE` for future narrow World Cup behavior tweaks.
- Performance-sensitive class:
  - Streaming/runtime architecture is performance-sensitive; this pass preserves the existing smoke/gate rather than claiming new capacity.
- Whether harness mapping must be extended:
  - No new workflow class required.
- Required performance evidence:
  - Local release gate plus DockerHost live smoke must prove async chat, stream success, and service health.
- Focused verification commands:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_policy.py tests/test_agent_factory.py tests/test_chat_behavior_eval.py -q`
  - `scripts/check_spec_contract.sh`
  - `scripts/check_harness_workflows.sh`
- Prerelease-grade verification commands:
  - `AI_BOUNDARY_APPROVED=1 SPEC_CONTRACT_APPROVED=1 make verify-release`
  - `envctl check-project --dir /Users/chris/AiProject/world-cup-chat-server`
  - `envctl validate-template --dir /Users/chris/AiProject/world-cup-chat-server/dockerhost`
  - DockerHost Git pull deploy plus `/healthz`, `/readyz`, `POST /chat`, and SSE `RUN_COMPLETED` smoke.

## Acceptance Criteria

- Functional:
  - New sibling directory exists and is a runnable project.
  - Runtime default policy identifies the assistant as World Cup Match Forecast Chat Server.
  - Mock chat smoke returns a World Cup-specific answer.
  - API title and primary docs identify the new project.
- Edge cases:
  - Hidden instruction and secret extraction remain refused.
  - Direct Polymarket order execution is refused by default.
  - Personal wallet/Polymarket account data requests are refused by default.
  - Language consistency guardrail still works.
- Compatibility:
  - Existing async chat/stream/run/conversation/RAG architecture imports and tests still pass.
  - DockerHost adapter uses the new project name and remains valid.
- Operational:
  - Release verification produces `.artifacts/release/summary.json`.
  - DockerHost environment can be deployed from a pushed Git ref and pass live smoke.
- Evidence artifacts:
  - Focused pytest output.
  - Release gate summary.
  - DockerHost validation output.
  - DockerHost deploy audit JSON and smoke transcript.

## Review Notes

- Open questions:
  - Final remote GitHub repository owner/name must be confirmed by actual remote creation or existing remote configuration.
  - Real Polymarket price discovery is intentionally deferred to a future spec.
- Accepted assumptions:
  - The reusable platform migration is the current FastAPI/PydanticAI/Celery/Redis/Postgres/Harness/DockerHost skeleton.
  - The first live smoke may use mock LLM and hash embeddings to prove deployability without provider secrets.
- Rejected alternatives:
  - Do not keep Ask this Agent or MOSS fixtures as active defaults.
  - Do not implement real-money Polymarket execution in this migration pass.
