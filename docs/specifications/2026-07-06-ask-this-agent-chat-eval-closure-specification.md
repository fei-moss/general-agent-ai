# 2026-07-06 Ask this Agent Chat Eval Closure Specification

## Context

- Spec ID: `SPEC-ASK-THIS-AGENT-CHAT-EVAL-CLOSURE-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- PRD/source request: 补齐 Ask this Agent 聊天效果评估优化闭环, 覆盖评估矩阵、Golden Case、真实模型回放、语义评审、中心化接口数据一致性、版本对比、线上样本沉淀和发布门禁。
- Target baseline: current `codex/zai-glm52-dockerhost` branch after Marketplace AI integration and identity no-tool model path fixes.
- Current behavior:
  - `tests/chat_eval/golden_cases.jsonl` contains behavior golden cases.
  - `tests/chat_eval/evaluator.py` validates case schema and deterministic guardrail expectations.
  - `tests/chat_eval/judge.py` runs allowed cases through an in-memory deterministic `FunctionModel`.
  - `tests/test_chat_behavior_eval.py` is covered indirectly by full pytest in `scripts/verify_release.sh`.
- Problem:
  - The existing framework is a useful first layer but does not define a coverage contract, live replay shape, judge rubric, data-field consistency checks, versioned scorecard, sample-ingestion workflow, or explicit release evidence.
  - Future prompt/tool/policy tuning can still become subjective unless every change produces comparable evaluation evidence.
- Non-goals:
  - Do not make live provider calls mandatory in local pytest or `make verify-release`.
  - Do not add a network-dependent LLM judge to release gates.
  - Do not store raw wallets, tokens, production logs, provider keys, or private payloads in fixtures.
  - Do not change public chat API behavior in this slice.

## Product Semantics

- User/operator workflow:
  - Engineers add product questions to `tests/chat_eval/golden_cases.jsonl`.
  - Each case is checked against `tests/chat_eval/coverage_contract.json`.
  - Local deterministic eval remains the fast release gate.
  - Optional live replay can call DockerHost `/chat` and `/stream/{run_id}` with operator-supplied auth.
  - Scorecards capture prompt/policy/model/dataset/git metadata so candidates can be compared against a baseline.
  - Bad online samples are sanitized into candidate golden cases before review.
- State model:
  - Eval datasets are repository fixtures.
  - Eval reports are generated artifacts under `.artifacts/` and are not committed.
  - Live replay is read-only from this service's perspective: it creates chat runs but performs no external money or account operations.
- Ownership and identity rules:
  - Server-owned eval metadata must not be controlled by user payload.
  - Wallet addresses in samples are redacted unless the case explicitly uses a synthetic fixture address.
  - Fixture payloads must use synthetic addresses, synthetic Agent ids, and non-secret tokens only.
- Permissions/authentication:
  - Live replay requires explicit `--base-url` and an auth token from an environment variable or non-committed operator input.
  - No auth token value is written to reports.
  - Live replay uses HTTP/1.1 for curl transport so DockerHost SSE streams are evaluated with stable framing.
- Empty, error, retry, timeout, duplicate, and partial-failure behavior:
  - Empty or duplicate case ids fail local validation.
  - Missing required coverage areas fail local validation.
  - Live replay classifies API, stream, timeout, and parse failures separately.
  - Scorecard failure distinguishes safety/data-fidelity blockers from softer quality regressions.
- Compatibility and migration expectations:
  - Existing golden cases remain valid.
  - Existing focused tests remain valid.
  - New optional fields are additive.

## API / Interface Contract

- Routes, commands, events, jobs, or UI surfaces:
  - New local commands:
    - `.venv/bin/python -m tests.chat_eval.scorecard --output .artifacts/release/chat_eval_scorecard.json --strict`
    - `.venv/bin/python -m tests.chat_eval.live_runner --base-url <url> --auth-token-env <env> --output .artifacts/release/chat_eval_live.json`
    - `.venv/bin/python -m tests.chat_eval.sample_ingestion --input <jsonl> --output <jsonl>`
  - New Make targets:
    - `make chat-eval`
    - `make chat-eval-report`
    - `make chat-eval-live`
- Request fields and validation:
  - Golden case optional fields:
    - `expected_sources`: list of source/tool names expected for factual/data cases.
    - `expected_fields`: list of page/interface fields the answer must handle.
    - `requires_wallet`: boolean, true only for synthetic wallet-context cases.
    - `fixture_proxy_payload`: object containing only synthetic eval payload values.
    - `risk_level`: `low`, `medium`, `high`, or `critical`.
    - `quality_axes`: list of rubric dimensions relevant to the case.
  - Live replay request body uses `message`, `stream=true`, `metadata`, and optional `proxy_payload` from `fixture_proxy_payload`.
  - Live replay may override synthetic fixture context with `CHAT_EVAL_AGENT_ADDRESS`, `CHAT_EVAL_WALLET_ADDRESS`, `--chain-id`, and `CHAT_EVAL_DROP_CHAIN_ID`/`--drop-chain-id` for real DockerHost endpoints.
- Response/envelope fields and types:
  - Scorecard report includes `status`, `metadata`, `summary`, `thresholds`, `blockers`, and `case_results`.
  - Live replay report includes per-case `run_id`, `trace_id`, `events`, `tool_calls`, `content`, `latency_ms`, and sanitized error details.
- Status/error codes:
  - CLI exits non-zero in `--strict` mode when required thresholds fail.
  - Live replay exits non-zero only when `--strict` is provided.
- Pagination/sorting/filtering:
  - CLI supports `--case-id` and `--tag` filters for live replay.
  - CLI supports `--exclude-tag` so legacy or unrelated case groups can be omitted from a focused live replay.
  - CLI supports live-only context overrides without mutating golden fixtures.
- Backward compatibility:
  - Existing pytest and release commands continue to work.

## Data / Schema / Projection Impact

- Tables, indexes, migrations, backfills:
  - None.
- Read models, projections, snapshots, caches:
  - None.
- Rebuild or cleanup operators:
  - None.
- Historical data behavior:
  - Existing eval cases stay valid.
- Performance-sensitive queries or write paths:
  - Local deterministic eval is in-memory and bounded by fixture size.
  - Live replay is explicitly opt-in and bounded by case filters or fixture count.

## Architecture

- Modules/files expected to change:
  - `tests/chat_eval/coverage_contract.json`
  - `tests/chat_eval/answer_rubric.json`
  - `tests/chat_eval/evaluator.py`
  - `tests/chat_eval/judge.py`
  - `tests/chat_eval/scorecard.py`
  - `tests/chat_eval/live_runner.py`
  - `tests/chat_eval/sample_ingestion.py`
  - `tests/chat_eval/golden_cases.jsonl`
  - `tests/test_chat_behavior_eval.py`
  - `tests/test_chat_eval_closure.py`
  - `Makefile`
  - `scripts/verify_release.sh`
  - matching spec and implementation plan.
- Data flow:
  1. Case loader validates JSONL shape, optional fields, and secret hygiene.
  2. Coverage contract verifies required areas, tags, risk levels, wallet/data cases, and minimum counts.
  3. Deterministic judge produces trait and forbidden-claim results.
  4. Scorecard combines judge output, coverage contract, rubric dimensions, thresholds, and version metadata.
  5. Optional live runner replays cases against `/chat` and stream endpoints, records model output and tool events, then writes a sanitized report.
  6. Sample ingestion sanitizes online bad samples into reviewable JSONL candidate cases.
- Transaction/concurrency boundaries:
  - Local eval has no DB or network transaction.
  - Live replay sends one request per selected case and treats each case independently.
  - Curl transport pins HTTP/1.1 for both `/chat` and `/stream/{run_id}` requests to avoid HTTP/2 stream framing differences in DockerHost checks.
- Observability/logging/metrics:
  - Scorecards include case ids, area summaries, threshold blockers, and metadata.
  - Live reports redact auth and common secret/wallet patterns.
- Rollback strategy:
  - Revert test/eval files, Make targets, and release hook. No data rollback.

## Harness Classification

- Expected gate(s):
  - `HARNESS-SPEC-FIRST-FEATURE`
  - focused pytest for chat eval
  - `scripts/check_spec_contract.sh`
  - `scripts/check_harness_workflows.sh`
  - `scripts/verify_release.sh`
- Performance-sensitive class:
  - Not runtime performance-sensitive.
- Whether harness mapping must be extended:
  - No.
- Required performance evidence:
  - Local eval remains bounded and deterministic; live replay remains opt-in.
- Focused verification commands:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_eval.py tests/test_chat_eval_closure.py -q`
  - `.venv/bin/python -m tests.chat_eval.scorecard --output /tmp/chat_eval_scorecard.json --strict`
- Prerelease-grade verification commands:
  - `AI_BOUNDARY_APPROVED=1 PYTHON=.venv/bin/python scripts/verify_release.sh`

## Acceptance Criteria

- Functional:
  - Coverage contract exists and validates all eight closure modules.
  - Golden cases include data-source, wallet-context, missing-field, chain-id, identity, FAQ, safety, and formatting examples.
  - Deterministic scorecard can be generated and fails in strict mode when thresholds fail.
  - Live replay runner can build sanitized API reports without writing auth tokens.
  - Sample ingestion converts sanitized online examples into candidate golden cases.
  - Make targets expose local, report, and live eval entrypoints.
  - Release gate explicitly runs chat eval and scorecard checks.
- Edge cases:
  - Synthetic wallet addresses are allowed only inside `fixture_proxy_payload`.
  - Real-looking secrets are rejected from fixtures and sanitized from sample ingestion.
  - Live replay stream parser handles token, tool, completion, and error events.
  - Live replay curl commands pin `--http1.1` for both POST and SSE stream reads.
  - Missing live auth fails with a clear local CLI error.
- Compatibility:
  - Existing golden cases and behavior tests continue to pass.
  - No public API, DB, or runtime route changes.
- Operational:
  - No external service is required for local verification.
  - Reports are written to caller-provided paths.
  - Live replay is opt-in and bounded.
- Evidence artifacts:
  - Spec and plan.
  - Coverage contract and rubric.
  - Scorecard JSON from focused verification.
  - Release harness output.

## Review Notes

- Open questions:
  - PM/legal may later refine rubric wording and pass thresholds for production launch.
  - LLM-as-judge provider choice remains future work; this slice defines the rubric and deterministic scorecard first.
- Accepted assumptions:
  - A deterministic scorecard is the correct release gate; live model eval is advisory until provider noise and cost policy are settled.
  - Synthetic wallet and Agent fixtures are enough to build the contract before upstream finalizes payload fields.
- Rejected alternatives:
  - Make live model eval mandatory in `verify-release`: rejected because it introduces network/provider flake into the release authority.
  - Add a database-backed eval service now: rejected because static fixtures and JSON artifacts are sufficient for this phase.
  - Treat prompt edits as the optimization mechanism: rejected because the target is a policy/eval/versioning workflow around the model.
- Reviewer findings and resolution:
  - Pending implementation review.
