# 2026-06-22 Z.AI GLM-5.2 Provider Specification

## Context

- Spec ID: `SPEC-ZAI-GLM52-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- PRD/source request: Read Z.AI technical documentation and complete the code needed to run this chat platform on DockerHost with Z.AI GLM-5.2 as the real underlying LLM.
- Primary documentation sources:
  - Z.AI Quick Start: `https://docs.z.ai/guides/overview/quick-start`
  - Z.AI Chat Completion API: `https://docs.z.ai/api-reference/llm/chat-completion`
  - Z.AI GLM-5.2 model guide: `https://docs.z.ai/guides/llm/glm-5.2`
  - Z.AI OpenAI Python SDK compatibility guide: `https://docs.z.ai/guides/develop/openai/python`
  - Z.AI Streaming Messages guide: `https://docs.z.ai/guides/capabilities/streaming`
  - Z.AI Function Calling guide: `https://docs.z.ai/guides/capabilities/function-calling`
  - Z.AI Migrate to GLM-5.2 guide: `https://docs.z.ai/guides/overview/migrate-to-glm-new`
- Current behavior:
  - Runtime supports `mock`, `openai`, `qwen`, `anthropic`, and `gemini`.
  - DockerHost stack defaults to `LLM_PROVIDER=mock`, so it cannot prove the real provider path.
  - OpenAI-compatible providers are already constructed through Pydantic AI `OpenAIChatModel`.
- Problem:
  - There is no first-class `zai` provider identity, secret contract, model mapping, provider limiter key, or DockerHost environment shape.
  - Operators would need to overload the `openai` provider and manually replace `OPENAI_BASE_URL`, which makes metrics, secret names, limiter keys, and run metadata misleading.
- Non-goals:
  - Do not add a frontend UI.
  - Do not deploy a live DockerHost environment in this change.
  - Do not store or request a real Z.AI API key in the repository.
  - Do not implement Z.AI native SDK. Use the documented OpenAI-compatible API path.
  - Do not add database schema changes.

## Product Semantics

- User/operator workflow:
  - Operator sets `LLM_PROVIDER=zai`.
  - Operator injects `ZAI_API_KEY` or `ZAI_API_KEY_FILE` from DockerHost secrets.
  - Runtime uses `ZAI_BASE_URL=https://api.z.ai/api/paas/v4/` and `ZAI_MODEL=glm-5.2` by default.
  - For a chat-only smoke, operator may set `RAG_ENABLED=false` and `EMBEDDING_PROVIDER=hash`; for full RAG, operator must inject the configured embedding provider secret.
  - `POST /chat` follows the existing realtime/batch routing and uses GLM-5.2 for real model calls.
  - The platform emits the same SSE/WebSocket events as other providers.
- State model:
  - No new run states.
  - Run plan metadata should continue to record provider/model through existing provider identity and limiter flow.
- Ownership and identity rules:
  - Provider identity is canonicalized as `(zai, glm-5.2)`.
  - Z.AI API key is a provider secret, not a user credential.
- Permissions/authentication:
  - No change to current demo application auth.
  - Missing Z.AI secret must fail fast for real provider startup/model construction.
- Empty, error, retry, timeout, duplicate, and partial-failure behavior:
  - Missing `zai_api_key` returns sanitized `PROVIDER_SECRET_MISSING`.
  - Provider 429/5xx continue through the existing provider error mapper and shared backoff path.
  - Provider limiter keys use `ratelimit:provider:zai:glm-5.2`.
  - No API key value may appear in logs, errors, Redis payloads, Postgres, docs, tests, or release artifacts.
- Compatibility and migration expectations:
  - Existing provider settings remain valid.
  - `openai` remains available for OpenAI.
  - `qwen` remains the DashScope-compatible provider.
  - `zai` is additive.

## API / Interface Contract

- Routes, commands, events, jobs, or UI surfaces:
  - Existing `/chat`, `/stream/{run_id}`, `/ws/{run_id}`, `/runs/{run_id}` surfaces are unchanged.
  - DockerHost env accepts `LLM_PROVIDER=zai`, `ZAI_MODEL`, `ZAI_BASE_URL`, `ZAI_API_KEY`, and `ZAI_API_KEY_FILE`.
- Request fields and validation:
  - No user-facing request field changes.
  - Server-side provider selection comes from environment configuration.
- Response/envelope fields and types:
  - No envelope change.
- Status/error codes:
  - Missing provider secret follows existing startup/model failure semantics.
  - Runtime provider limiter denials continue to produce existing 429/503 behavior.
- Backward compatibility:
  - Existing tests and local mock mode must keep passing without Z.AI credentials.

## Data / Schema / Projection Impact

- Tables, indexes, migrations, backfills:
  - None.
- Read models, projections, snapshots, caches:
  - Redis limiter/backoff keys add provider/model entries for `zai:glm-5.2`.
- Rebuild or cleanup operators:
  - None.
- Historical data behavior:
  - Existing runs remain unchanged.
- Performance-sensitive queries or write paths:
  - Provider limiter still runs once per model request, not per streamed token.

## Architecture

- Modules/files expected to change:
  - `app/core/config.py`
  - `app/core/secrets.py`
  - `app/runtime/provider_limits.py`
  - `app/runtime/agent_factory.py`
  - `.env.example`
  - `dockerhost/compose.yaml`
  - `dockerhost/env.example`
  - focused tests under `tests/`
- Data flow:
  1. `Settings` loads Z.AI base URL, model, and secret fields.
  2. `SecretProvider` maps provider `zai` to `zai_api_key`.
  3. `provider_identity_from_settings()` returns `ProviderIdentity("zai", "glm-5.2")`.
  4. `build_model()` constructs Pydantic AI `OpenAIChatModel` with `OpenAIProvider(base_url=ZAI_BASE_URL, api_key=ZAI_API_KEY)`.
  5. Optional GLM-specific request body settings are passed via OpenAI-compatible `extra_body`.
- Transaction/concurrency boundaries:
  - No changes.
- Observability/logging/metrics:
  - Existing provider limiter metrics use provider label `zai` and model label `glm-5.2`.
- Rollback strategy:
  - Set `LLM_PROVIDER=mock` to return to the offline path.
  - Existing providers are unaffected.

## Harness Classification

- Expected gate(s):
  - `ai_boundaries`
  - `spec_contract`
  - focused provider/secret/model tests
  - full `pytest`
- Performance-sensitive class:
  - Provider hot path only; no DB or schema changes.
- Whether harness mapping must be extended:
  - No.
- Required performance evidence:
  - Live DockerHost GLM-5.2 smoke and small TTFT benchmark are required before claiming the real service is fully walked.
- Focused verification commands:
  - `.venv/bin/python -m pytest tests/test_agent_factory.py tests/test_secret_management.py tests/test_provider_rate_limits.py -q`
- Prerelease-grade verification commands:
  - `make verify-release`

## Acceptance Criteria

- Functional:
  - `LLM_PROVIDER=zai` builds an `OpenAIChatModel` with model `glm-5.2`.
  - Z.AI secret validation accepts `ZAI_API_KEY` / `ZAI_API_KEY_FILE`.
  - Provider limiter identity is `zai:glm-5.2`.
  - DockerHost can be configured for `LLM_PROVIDER=zai` without committing any secret.
- Edge cases:
  - Missing Z.AI secret fails with sanitized `PROVIDER_SECRET_MISSING`.
  - Local mock remains zero-key.
- Compatibility:
  - Existing providers remain unchanged.
- Operational:
  - DockerHost environment documents how to inject `ZAI_API_KEY`.
- Evidence artifacts:
  - Focused test output.
  - Release summary when run.
  - Future live DockerHost smoke output after a real secret is supplied.

## Review Notes

- Open questions:
  - Real Z.AI account RPM/TPM limits are account-specific and must be configured by the operator.
- Accepted assumptions:
  - Z.AI's OpenAI-compatible endpoint is the integration path.
  - `zai` is clearer than overloading `openai` for metrics and secret naming.
- Rejected alternatives:
  - Rejected using `LLM_PROVIDER=openai` with `OPENAI_BASE_URL=https://api.z.ai/api/paas/v4/` because it would mislabel metrics, limiter keys, and missing-secret errors.
