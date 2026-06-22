# 2026-06-22 Z.AI GLM-5.2 Provider Implementation Plan

## Plan Header

- Specification: `docs/specifications/2026-06-22-zai-glm52-provider-specification.md`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Target branch/baseline: `main`
- Scope summary: Add first-class `zai` provider support using Z.AI's OpenAI-compatible GLM-5.2 endpoint and prepare DockerHost configuration for a real-service smoke.
- Out of scope:
  - Live DockerHost deployment.
  - Real API key creation or storage.
  - Frontend work.
  - Database migrations.

## Change Steps

1. Provider settings and secret contract
   - Files/modules:
     - `app/core/config.py`
     - `app/core/secrets.py`
   - Behavior change:
     - Add `zai_base_url`, `zai_api_key`, `zai_api_key_file`, `zai_model`, and optional GLM-5.2 tuning settings.
     - Map provider `zai` to `zai_api_key`.
   - Data contract impact:
     - Environment-only configuration.
   - Tests to add/update:
     - Missing Z.AI secret fails sanitized.
     - File-injected Z.AI secret loads.
   - Verification command:
     - `.venv/bin/python -m pytest tests/test_secret_management.py -q`
   - Rollback or compatibility note:
     - Existing provider env remains unchanged.
     - Root `.env.example` is intentionally untouched because repository AI boundaries forbid `.env*` edits; DockerHost-specific examples live under `dockerhost/env.example`.

2. Runtime provider identity and model construction
   - Files/modules:
     - `app/runtime/provider_limits.py`
     - `app/runtime/agent_factory.py`
   - Behavior change:
     - Provider limiter identity resolves `LLM_PROVIDER=zai` to `zai/glm-5.2`.
     - Model factory builds `OpenAIChatModel` with Z.AI base URL and API key.
     - GLM-specific `thinking`, `reasoning_effort`, and `tool_stream` request options are available through `extra_body`.
   - Data contract impact:
     - Redis limiter key adds `ratelimit:provider:zai:glm-5.2`.
   - Tests to add/update:
     - Agent factory builds OpenAI-compatible model for Z.AI.
     - Provider identity test.
   - Verification command:
     - `.venv/bin/python -m pytest tests/test_agent_factory.py tests/test_provider_rate_limits.py -q`
   - Rollback or compatibility note:
     - `LLM_PROVIDER=mock` bypass remains unchanged.

3. DockerHost real-provider configuration
   - Files/modules:
     - `dockerhost/compose.yaml`
     - `dockerhost/env.example`
   - Behavior change:
     - Compose reads `LLM_PROVIDER`, `ZAI_MODEL`, `ZAI_BASE_URL`, and secret-related env from DockerHost rather than hardcoding only mock.
     - Compose allows RAG/embedding env overrides so a chat-only GLM smoke can disable RAG or use hash embeddings.
   - Data contract impact:
     - DockerHost operator must inject `ZAI_API_KEY` or file-based equivalent for `LLM_PROVIDER=zai`.
     - Full RAG environments must still inject the configured embedding provider secret.
   - Tests to add/update:
     - No unit test required; docs/config inspection.
   - Verification command:
     - `envctl validate-template --dir /Users/chris/AiProject/general-agent-ai/dockerhost` when envctl is available.
   - Rollback or compatibility note:
     - Defaults remain mock for zero-key local deploys.

4. Focused verification
   - Files/modules:
     - tests only.
   - Behavior change:
     - None.
   - Data contract impact:
     - None.
   - Tests to add/update:
     - Run focused provider tests.
   - Verification command:
     - `.venv/bin/python -m pytest tests/test_agent_factory.py tests/test_secret_management.py tests/test_provider_rate_limits.py -q`
   - Rollback or compatibility note:
     - Full `make verify-release` remains the release gate.

## Risk Controls

- Public contract risks:
  - Avoid changing `/chat` envelope or event types.
- Money/accounting/security risks:
  - Never commit a real Z.AI key.
  - Keep provider limiter fail-closed by default.
- Migration/rebuild risks:
  - No DB migration.
- Performance risks:
  - Real GLM-5.2 latency is unverified until DockerHost smoke and benchmark run with a real key.
- Deployment/test-branch risks:
  - DockerHost currently deploys from pushed refs; live smoke requires a pushed branch/commit and secret injection.
- Unrelated local changes to avoid:
  - Do not stage `.artifacts/`, `.env`, or local runbooks.

## Completion Criteria

- Specification still matches implementation.
- Focused provider/secret tests pass.
- DockerHost config exposes Z.AI provider settings without secrets.
- Any skipped live DockerHost verification is reported as a residual blocker.
