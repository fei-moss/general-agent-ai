---
spec_id: SPEC-CHAT-OUTPUT-COMPLETION-001
module: chat_output_completion
status: approved
workflow_class: HARNESS-SPEC-FIRST-FEATURE
---

# Chat Output Completion

## Specification

### Behavior

- `SPEC-CHAT-OUTPUT-COMPLETION-001-R1`: Chat Server records the final provider `finish_reason` in the run plan after model execution without exposing provider internals or secrets in public errors.
- `SPEC-CHAT-OUTPUT-COMPLETION-001-R2`: a final `finish_reason=length` is not persisted or emitted as a successful complete answer. The run converges to `FAILED`, emits a stable `ERROR` with `stage=model_output` and `error=OUTPUT_TRUNCATED`, and then emits `RUN_COMPLETED` with `status=FAILED`.
- `SPEC-CHAT-OUTPUT-COMPLETION-001-R3`: normal `stop` and absent finish reasons preserve the current `TOKEN`, assistant-message, and `RUN_COMPLETED/SUCCEEDED` contract.
- `SPEC-CHAT-OUTPUT-COMPLETION-001-R4`: the repository default provider output budget is 4096 tokens in application settings and every DockerHost runtime service that performs or accounts for runs. A future redeploy or recreate must not fall back to 1024 tokens when no environment override is supplied.

### Invariants

- Provider admission and settlement still use the configured maximum output budget; increasing the default must not bypass quota reservation, backoff, or fail-closed settlement.
- Partial model text already streamed before a length stop is never re-labelled as complete or persisted as the assistant's successful final answer.
- The stable error contains no raw provider response, prompt, tool arguments, credentials, or partial answer.
- The behavior is identical in realtime and Celery execution because both use the same orchestrator and settings contract.

### Performance And Compatibility

- Public API paths and response schemas are unchanged.
- Successful runs retain the existing terminal content fallback.
- DockerHost `api`, `worker`, and `reaper` share the 4096-token default so redeploy and rollback behavior is deterministic from the pushed repository ref.

## Implementation Plan

1. Add failing tests for finish-reason extraction, length-stop failure convergence, ordinary success compatibility, application defaults, and DockerHost service defaults.
2. Return typed model-output metadata from orchestration, persist `finish_reason` into the run plan, and add a dedicated sanitized truncation handler before the generic fatal path.
3. Raise the repository-owned default output budget to 4096 across settings and DockerHost services while retaining provider quota reservation and settlement.
4. Run focused pytest, `make verify-change`, commit, and run clean `make verify-release` with owner approval.
5. Redeploy the pushed ref to the existing DockerHost branch space and verify a long Marketplace answer reaches a complete terminal event; retain the previous SHA for rollback.

## Closeout Evidence

- Focused tests: RED proved the previous `length` path returned partial text and the previous repository/DockerHost default was 1024; GREEN passed `tests/test_orchestrator.py`, `tests/test_marketplace_deployment_contract.py`, `tests/test_agent_factory.py`, `tests/test_provider_rate_limits.py`, and `tests/test_secret_management.py`.
- Full tests: `/Users/chris/AiProject/general-agent-ai/.venv/bin/python -m pytest -q` passed with one existing skip.
- Review or approval: `2026-07-20-owner-request-chat-reliability-fix`
- Change gate: `AI_BOUNDARY_APPROVED=1 AI_BOUNDARY_APPROVAL_EVIDENCE=owner-request:chat-reliability-fix-2026-07-20 VERIFY_ACTIVE_SPEC_ID=SPEC-CHAT-OUTPUT-COMPLETION-001 VERIFY_COMPARE_REF=origin/codex/zai-glm52-dockerhost make verify-change VENV=/Users/chris/AiProject/general-agent-ai/.venv` passed.
- Release command: pending clean-commit verification.
- Runtime evidence: pending DockerHost redeploy.
- Residual risk: Marketplace's separate 30-second SSE proxy deadline remains until the Marketplace-side prompt is implemented and deployed.
