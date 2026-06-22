# 2026-06-22 Internal RAG Boundary Implementation Plan

## Plan Header

- Specification: `docs/specifications/2026-06-22-internal-rag-boundary-specification.md`
- Spec ID: `SPEC-INTERNAL-RAG-BOUNDARY-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Scope summary: Reclassify RAG as an internal management plane, prevent ordinary users from directly selecting or querying KBs, and let normal Chat consume a server-selected internal KB.
- Out of scope:
  - Formal OAuth/API-key authentication.
  - Tenant/RBAC model.
  - RAG management UI.
  - Migration of existing knowledge-base ownership rows.

## Change Steps

### Step 1: Add Internal RAG Boundary Tests

- Files/modules:
  - `tests/test_rag_api.py`
  - `tests/test_orchestrator.py`
  - `tests/test_rag_agent_tool.py`
  - `tests/test_rag_service.py`
- Behavior:
  - Assert `/rag/*` guard fails closed for non-admin users.
  - Assert admin users pass the guard.
  - Assert Chat ignores client `metadata.knowledge_base_id` by default.
  - Assert Chat uses server default KB when configured.
  - Assert retriever and query service separate real requester from KB owner.
- Verification:
  - `.venv/bin/python -m pytest tests/test_rag_api.py tests/test_orchestrator.py tests/test_rag_agent_tool.py tests/test_rag_service.py -q`

### Step 2: Add RAG Boundary Configuration

- Files/modules:
  - `app/core/config.py`
  - `dockerhost/compose.yaml`
  - `dockerhost/env.example`
- Behavior:
  - Add `rag_admin_user_ids`, `rag_default_knowledge_base_id`, `rag_internal_owner_user_id`, and `rag_allow_client_knowledge_base_id`.
  - Thread these values into API and worker containers.
- Verification:
  - `docker compose -f dockerhost/compose.yaml config`

### Step 3: Guard Internal RAG Routes

- Files/modules:
  - `app/api/routers/rag.py`
- Behavior:
  - Add a fail-closed admin assertion using `RAG_ADMIN_USER_IDS`.
  - Apply it to all `/rag/*` handlers before repository or service use.
  - Preserve existing owner-scoped behavior inside the internal plane.
- Verification:
  - `.venv/bin/python -m pytest tests/test_rag_api.py -q`

### Step 4: Rebind Chat RAG Selection To Server Configuration

- Files/modules:
  - `app/runtime/orchestrator.py`
  - `app/runtime/adapters.py`
  - `app/rag/service.py`
- Behavior:
  - Replace metadata-only KB selection with server-side selection.
  - Keep client KB selection disabled by default.
  - Pass internal KB owner separately from the real requester.
  - Keep retrieval logs tied to the real requester.
- Verification:
  - `.venv/bin/python -m pytest tests/test_orchestrator.py tests/test_rag_agent_tool.py tests/test_rag_service.py -q`

### Step 5: Update Integration Documentation

- Files/modules:
  - `docs/INTEGRATION_GUIDE.md`
- Behavior:
  - Make the ordinary integration path Chat-only.
  - Document `/rag/*` as internal-only.
  - Remove instructions telling normal callers to pass `metadata.knowledge_base_id`.
- Verification:
  - Manual doc review plus release checks.

### Step 6: Release Verification

- Commands:
  - `.venv/bin/python -m pytest tests/test_rag_api.py tests/test_orchestrator.py tests/test_rag_agent_tool.py tests/test_rag_service.py -q`
  - `docker compose -f dockerhost/compose.yaml config`
  - `AI_BOUNDARY_APPROVED=1 make verify-release`
- Evidence:
  - Focused test output.
  - Docker Compose config validation.
  - `.artifacts/release/summary.json`.
