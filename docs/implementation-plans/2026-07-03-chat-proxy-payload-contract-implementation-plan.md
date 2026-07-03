# 2026-07-03 Chat Proxy Payload Contract Implementation Plan

Specification: `SPEC-CHAT-PROXY-PAYLOAD-CONTRACT-001`

Target branch/baseline: `codex/zai-glm52-dockerhost`

Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`

## Scope Summary

Add `proxy_payload` as the only upstream-facing context field for `POST /chat`, expose it to the existing runtime context pipeline, reject external `run_context`, and update focused documentation.

## Out Of Scope

- Marketplace API changes.
- Wallet authentication or full wallet data ingestion.
- Database migrations.
- Stream/WebSocket/run response shape changes.

## Change Steps

1. Schema tests and normalization
   - Files/modules: `app/core/schemas.py`, `tests/test_chat_routing.py`.
   - Behavior change: `ChatRequest` accepts `proxy_payload`, exposes it to the runtime, and rejects request bodies that contain `run_context`.
   - Data contract impact: additive request field.
   - Tests to add/update: schema acceptance, `run_context` rejection, `_build_payload` forwarding.
   - Verification command: `.venv/bin/python -m pytest tests/test_chat_routing.py -q`.
   - Rollback or compatibility note: restore `run_context` request-field compatibility only if an active caller is discovered.

2. Idempotency and provider preflight regression
   - Files/modules: `tests/test_idempotency_and_lock.py`, existing chat router paths.
   - Behavior change: prove normalized `proxy_payload` participates in idempotency and provider-token estimates through the effective runtime context.
   - Data contract impact: context changes remain replay-safe.
   - Tests to add/update: hash differs when `proxy_payload` differs after normalization.
   - Verification command: `.venv/bin/python -m pytest tests/test_idempotency_and_lock.py tests/test_chat_routing.py -q`.
   - Rollback or compatibility note: no persistent data impact.

3. Docs
   - Files/modules: `docs/API.md`, `docs/INTEGRATION_GUIDE.md`.
   - Behavior change: examples show valid JSON with `proxy_payload`.
   - Data contract impact: document `proxy_payload` as the only external context field.
   - Tests to add/update: none.
   - Verification command: manual review plus focused tests.
   - Rollback or compatibility note: docs-only.

4. Review and verification
   - Files/modules: changed files.
   - Behavior change: defect-finding pass for ambiguity, redaction, and contract drift.
   - Tests to add/update: any missing regression found during review.
   - Verification command: `.venv/bin/python -m pytest tests/test_chat_routing.py tests/test_idempotency_and_lock.py -q`.

## Risk Controls

- Public contract risks: reject `run_context` explicitly instead of silently ignoring it.
- Money/accounting/security risks: documentation warns against passing private keys, raw secrets, or unrelated wallet data.
- Migration/rebuild risks: none.
- Performance risks: minimal; context token estimation already exists.
- Deployment/test-branch risks: no deployment performed by this plan unless separately requested.
- Unrelated local changes to avoid: stage only spec, plan, schema, focused tests, and docs for this change.

## Completion Criteria

- Specification still matches implementation.
- Focused tests pass.
- `proxy_payload` examples are valid JSON.
- Review finds no unresolved contract or security issues.
