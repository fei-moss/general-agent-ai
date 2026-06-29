# 2026-06-24 Streaming Output Guardrail Specification

- Spec ID: `SPEC-STREAMING-OUTPUT-GUARDRAIL-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Related specifications:
  - `SPEC-CHAT-RUNTIME-001`: realtime Chat runtime and TTFT contract.
  - `SPEC-CHAT-BEHAVIOR-POLICY-001`: deterministic chat behavior policy and guardrails.

## Context

- PRD/source request:
  - Review finding: `SPEC-CHAT-BEHAVIOR-POLICY-001` implemented output guardrails by buffering the complete assistant answer before emitting any `TOKEN`, which prevents unsafe token leakage but regresses the platform's first-priority realtime streaming and TTFT contract.
- Target baseline:
  - Branch `codex/zai-glm52-dockerhost` at `781ee3be73500cdfde29833a4b99262b693c8a3c`.
- Current behavior:
  - `AgentOrchestrator._run_agent()` collects all token chunks.
  - `_apply_output_guardrail()` reviews the complete answer.
  - `_emit_token_chunks()` emits all `TOKEN` events only after model generation has completed.
- Problem:
  - For allowed output, observed TTFT is effectively full model generation time rather than first safe token time.
  - `TokenAggregator` still preserves "first chunk flushes immediately" semantics internally, but the outer buffering path prevents those chunks from reaching the event bus during generation.
  - The current TTFT test only proves a metric is recorded; it does not prove the first `TOKEN` is emitted before model completion.
- Non-goals:
  - No new public API field, event type, database schema, provider limiter behavior, external moderation dependency, or LLM judge.
  - No attempt to guarantee semantic safety beyond the deterministic high-confidence leak patterns already in `SPEC-CHAT-BEHAVIOR-POLICY-001`.
  - No load-test implementation in this slice; performance evidence here is focused on restoring streaming behavior at the unit/integration level.

## Product Semantics

- User/operator workflow:
  - Clients continue to submit `POST /chat`, receive HTTP `202`, and subscribe to SSE/WebSocket streams.
  - For allowed model output, clients receive the first safe `TOKEN` before model generation completes.
  - For refused output, clients never receive a high-confidence hidden-instruction or secret leak through `TOKEN`.
  - If the output guardrail blocks generated text, the stream emits a sanitized `ERROR` event with `stage=output_guardrail` and then completes with the deterministic safe replacement text; raw unsafe text is never included in the event payload.
- State model:
  - Successful runs still converge to `RUN_COMPLETED` with `status=SUCCEEDED`.
  - If a leak is detected after a safe prefix was already emitted, the final assistant answer is the emitted safe prefix plus the deterministic safe response. `RUN_COMPLETED.data.content` and persisted assistant content must match the concatenated `TOKEN` stream.
- Ownership and identity rules:
  - Unchanged.
- Permissions/authentication:
  - Unchanged.
- Empty, error, retry, timeout, duplicate, and partial-failure behavior:
  - Empty model output still uses the existing fallback answer.
  - Provider limiter, retries, run failure convergence, idempotency, and conversation lock behavior are unchanged.
  - If event publication fails, existing best-effort event handling remains unchanged.
- Compatibility and migration expectations:
  - Existing clients that concatenate `TOKEN.data.token` remain compatible.
  - Existing clients that use `RUN_COMPLETED.data.content` as a final fallback remain compatible.
  - Historical runs are unaffected.

## API / Interface Contract

- Routes, commands, events, jobs, or UI surfaces:
  - `/chat`, `/stream/{agent_run_id}`, `/ws/{agent_run_id}`, `/runs/{agent_run_id}` are unchanged.
  - `TOKEN.data` remains `{"token": "<safe-delta-or-aggregated-text>"}`.
  - `RUN_COMPLETED.data.content` remains the final assistant answer.
- Request fields and validation:
  - Unchanged.
- Response/envelope fields and types:
  - Unchanged.
- Status/error codes:
  - Unchanged.
- Events:
  - Existing `ERROR` event may be emitted for output-guardrail replacement with `data.stage="output_guardrail"`, `category`, `reason_code`, and `safe_response`.
  - This `ERROR` event is not a run failure; `RUN_COMPLETED.data.status` remains `SUCCEEDED` when the safe replacement answer is persisted.
- Pagination/sorting/filtering:
  - Unchanged.
- Backward compatibility:
  - The only intentional behavior change is timing: allowed safe tokens are emitted during generation instead of after generation.

## Data / Schema / Projection Impact

- Tables, indexes, migrations, backfills:
  - None.
- Read models, projections, snapshots, caches:
  - None.
- Rebuild or cleanup operators:
  - None.
- Historical data behavior:
  - Historical runs remain readable.
- Performance-sensitive queries or write paths:
  - Streaming output guardrail must be local, deterministic, and allocation-bounded by the configured tail window plus incoming chunk size.
  - No DB session may be held while model streaming is in progress.
  - Provider limiter remains one admission/settlement operation per model request, not per token.

## Architecture

- Modules/files expected to change:
  - `app/runtime/chat_behavior.py`: expose deterministic output-leak patterns and a streaming/tail-window output guardrail helper.
  - `app/runtime/orchestrator.py`: apply the streaming output guardrail inside the model text stream loop and emit safe chunks during generation.
  - `tests/test_chat_behavior_policy.py`: focused helper coverage for tail-window behavior and split leak detection.
  - `tests/test_orchestrator.py`: integration coverage proving allowed output emits `TOKEN` before model completion and split leaks do not reach `TOKEN`.
  - `README.md`, `docs/API.md`, and `app/api/routers/chat.py`: documentation/docstring drift about realtime vs Celery execution.
- Data flow:
  1. API accepts the run as before.
  2. Orchestrator evaluates input guardrail as before.
  3. For allowed input, the Pydantic AI model stream produces raw text deltas.
  4. A streaming output guardrail keeps a sliding tail window of at least 64 characters and at least as long as the longest deterministic leak pattern minus one character.
  5. Prefix text that cannot become part of a future high-confidence leak is released to `TokenAggregator`.
  6. `TokenAggregator` emits the first safe chunk immediately and aggregates subsequent safe chunks by existing window/count rules.
  7. On finalization, any remaining safe tail is emitted; if the final tail reveals a leak, only the deterministic safe response is emitted.
  8. Persisted assistant content and `RUN_COMPLETED.data.content` are built from emitted safe chunks, not from unsafe raw model output.
- Transaction/concurrency boundaries:
  - No new lock, Redis key, queue, or DB transaction boundary.
  - The guardrail must not introduce waits, external calls, or provider calls.
- Observability/logging/metrics:
  - `chat_ttft_seconds` continues to be observed on first `TOKEN`, but now measures first safe token emission rather than full-answer completion for allowed output.
  - `ERROR stage=output_guardrail` is a policy replacement signal and must not be counted as a provider error.
  - Logs must not include unsafe raw output or hidden instruction/secret text.
- Rollback strategy:
  - Revert runtime/test/doc changes; no migration or data rollback is required.

## Harness Classification

- Expected gate(s):
  - `HARNESS-SPEC-FIRST-FEATURE`
  - `scripts/check_ai_boundaries.sh`
  - `scripts/check_spec_contract.sh`
  - `scripts/check_harness_workflows.sh`
  - Focused pytest and `scripts/verify_release.sh`
- Performance-sensitive class:
  - Realtime streaming hot path.
- Whether harness mapping must be extended:
  - No; existing `HARNESS-SPEC-FIRST-FEATURE` covers runtime behavior changes.
- Required performance evidence:
  - Focused orchestrator test proves a safe `TOKEN` is observable before the model stream is allowed to finish.
  - Existing/updated TTFT metric test proves the first safe `TOKEN` records TTFT.
  - Release smoke/load evidence remains a separate follow-up for concurrent TTFT p95 and stream lag.
- Focused verification commands:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_policy.py tests/test_orchestrator.py -q`
  - `scripts/check_ai_boundaries.sh`
  - `scripts/check_spec_contract.sh`
  - `scripts/check_harness_workflows.sh`
- Prerelease-grade verification commands:
  - `scripts/verify_release.sh`
  - `make verify-release`

## Acceptance Criteria

- Functional:
  - Allowed model output emits at least one `TOKEN` before model generation completes.
  - First released safe chunk is flushed immediately through the existing token aggregation semantics.
  - Split high-confidence leak patterns are detected even when the leak spans multiple provider chunks.
  - High-confidence secret values such as provider-looking API keys and private-key blocks are blocked by deterministic regex patterns.
  - The default streaming tail window retains at least 64 characters.
  - High-confidence hidden-instruction and secret leak text never appears in `TOKEN` events.
  - Output guardrail replacement emits a sanitized `ERROR stage=output_guardrail` event without raw unsafe text.
  - Persisted assistant content equals `RUN_COMPLETED.data.content`.
  - Concatenated `TOKEN.data.token` equals `RUN_COMPLETED.data.content` for successful allowed and output-guardrail-refused runs.
- Edge cases:
  - Leak at the beginning of output emits no raw unsafe prefix.
  - Leak after a benign prefix preserves the already-emitted benign prefix and completes with the safe response.
  - Safe output shorter than the tail window is emitted on finalization.
  - Empty output still uses the existing fallback answer.
- Compatibility:
  - No event type, request, response, schema, provider, or route contract changes.
- Operational:
  - No real provider key, token, hidden prompt, private log, or unsafe raw model response is written to docs/tests/logs.
  - No external service is required for focused tests.
- Evidence artifacts:
  - This specification and matching implementation plan.
  - Focused pytest output.
  - Harness/release output or explicit blocker.

## Review Notes

- Open questions:
  - The exact tail-window length should be computed from deterministic leak patterns, not hard-coded in multiple places.
  - A future classifier/judge may require a different streaming safety model; this spec is limited to deterministic high-confidence patterns.
- Accepted assumptions:
  - A bounded deterministic tail window is sufficient for the current local output guardrail scope.
  - Safe prefix emission is preferable to full-answer buffering when it preserves the no-leak contract.
  - If output is refused after a safe prefix, final content may include that safe prefix plus the safe refusal response.
- Rejected alternatives:
  - Continue full-answer buffering: rejected because it violates the realtime TTFT contract.
  - Emit raw tokens and redact after completion: rejected because already-sent SSE/WebSocket events cannot be retracted.
  - Add an external moderation service in the stream loop: rejected because it adds hot-path latency, availability coupling, and release-gate complexity outside this slice.
- Reviewer findings and resolution:
  - Finding: `SPEC-CHAT-BEHAVIOR-POLICY-001` line 114 explicitly traded off realtime token flush for v0 safety.
  - Resolution: this spec supersedes that tradeoff with a deterministic sliding-tail output guardrail.
