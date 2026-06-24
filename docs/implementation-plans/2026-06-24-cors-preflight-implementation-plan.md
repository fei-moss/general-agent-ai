# 2026-06-24 CORS Preflight Implementation Plan

## Plan Header

- Specification: `docs/specifications/2026-06-24-cors-preflight-specification.md`
- Spec ID: `SPEC-CORS-PREFLIGHT-001`
- Workflow Class: `HARNESS-FOCUSED-CHANGE`
- Target branch/baseline: current `codex/zai-glm52-dockerhost` worktree
- Scope summary: Fix browser CORS preflight for `/chat` by making CORSMiddleware outermost while preserving protected request auth.
- Out of scope:
  - Production origin allowlist design, auth model changes, route/schema/event/runtime changes, deployment changes.

## Change Steps

### Step 1: Add Failing CORS Regression Tests

- Files/modules:
  - `tests/test_cors.py`
- Behavior change:
  - None; tests express desired behavior before implementation.
- Data contract impact:
  - None.
- Tests to add/update:
  - Browser-style `OPTIONS /chat` with `Origin`, `Access-Control-Request-Method: POST`, and requested `Authorization, Content-Type` headers returns CORS headers and not `401`.
  - Browser-style unauthenticated `POST /chat` still returns `401` but includes `Access-Control-Allow-Origin`.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_cors.py -q`
- Rollback or compatibility note:
  - Expected to fail before middleware ordering is fixed.

### Step 2: Register CORS Outermost

- Files/modules:
  - `app/api/main.py`
- Behavior change:
  - Move CORS middleware registration after custom middleware registration so it wraps trace/auth/rate-limit middleware.
  - Keep existing `allow_origins`, `allow_credentials`, `allow_methods`, and `allow_headers` policy unchanged.
- Data contract impact:
  - None.
- Tests to add/update:
  - `tests/test_cors.py`
- Verification command:
  - `.venv/bin/python -m pytest tests/test_cors.py -q`
- Rollback or compatibility note:
  - Reverting this file restores previous behavior.

### Step 3: Update Frontend-Facing Docs

- Files/modules:
  - `docs/API.md`
- Behavior change:
  - Clarify that browser preflight is handled before auth and real `POST /chat` still requires credentials.
- Data contract impact:
  - None.
- Tests to add/update:
  - None.
- Verification command:
  - `scripts/check_spec_contract.sh`
- Rollback or compatibility note:
  - Documentation-only.

### Step 4: Harness Verification

- Files/modules:
  - All changed files.
- Behavior change:
  - None beyond implementation.
- Data contract impact:
  - None.
- Tests to add/update:
  - Fix only CORS-related failures.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_cors.py tests/test_chat_routing.py -q`
  - `make test`
  - `AI_BOUNDARY_APPROVED=1 make verify-release`
- Rollback or compatibility note:
  - If release gate fails for unrelated environment reasons, preserve focused evidence and report blocker.

## Risk Controls

- Public contract risks:
  - No route/schema/event changes.
  - Protected application requests still require auth.
- Money/accounting/security risks:
  - Do not relax real request authentication or provider guardrails.
  - Do not commit production frontend origin secrets or tokens.
- Migration/rebuild risks:
  - None.
- Performance risks:
  - Middleware ordering only; preflight avoids application side effects.
- Deployment/test-branch risks:
  - `app/api/main.py` is approval-required under `.ai-boundaries.yml`; run release gate with explicit owner approval.
- Unrelated local changes to avoid:
  - Do not modify streaming guardrail changes except as required by shared release checks.

## Completion Criteria

- Focused CORS tests pass.
- Existing focused chat routing tests pass.
- `make test` passes.
- `AI_BOUNDARY_APPROVED=1 make verify-release` passes or a concrete blocker is reported.
- Review finds no auth bypass for real protected requests.
