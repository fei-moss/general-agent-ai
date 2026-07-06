# 2026-07-06 Ask this Agent Chat Eval Closure Implementation Plan

## Plan Header

- Specification: `docs/specifications/2026-07-06-ask-this-agent-chat-eval-closure-specification.md`
- Spec ID: `SPEC-ASK-THIS-AGENT-CHAT-EVAL-CLOSURE-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Target branch/baseline: `codex/zai-glm52-dockerhost`
- Scope summary: Complete the current chat eval framework into a practical closure loop: coverage contract, expanded golden cases, deterministic scorecard, optional live replay, data-source checks, sample ingestion, version metadata, Make targets, and release-gate wiring.
- Out of scope:
  - Public API changes, DB migrations, mandatory live provider calls, external LLM judge dependency, production analytics ingestion.

## Change Steps

### Step 1: Evaluation Contract And Rubric

- Files/modules:
  - `tests/chat_eval/coverage_contract.json`
  - `tests/chat_eval/answer_rubric.json`
  - `tests/chat_eval/evaluator.py`
  - `tests/test_chat_eval_closure.py`
- Behavior change:
  - Adds coverage contract checks for areas, tags, risk levels, data-field cases, wallet-context cases, and thresholds.
  - Adds rubric dimensions for correctness, completeness, boundary safety, data faithfulness, presentation, and language consistency.
- Data contract impact:
  - Additive optional golden-case fields only.
- Tests to add/update:
  - Contract schema and coverage tests.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_eval.py tests/test_chat_eval_closure.py -q`
- Rollback or compatibility note:
  - Existing cases remain valid because new fields are optional except when required by coverage contract.

### Step 2: Product Golden Cases And Data Consistency Fields

- Files/modules:
  - `tests/chat_eval/golden_cases.jsonl`
  - `tests/chat_eval/judge.py`
- Behavior change:
  - Adds cases for wallet-context PnL, missing wallet context, wrong chain id, AUM, Top Holders, Live Activities, ai-compute volume, FAQ, identity, and formatting quality.
  - Extends deterministic answers and trait matching for new cases.
- Data contract impact:
  - Cases use synthetic fixture payloads only.
- Tests to add/update:
  - Existing eval tests plus new data consistency coverage tests.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_chat_behavior_eval.py tests/test_chat_eval_closure.py -q`
- Rollback or compatibility note:
  - Remove added JSONL rows and deterministic answers if reverted.

### Step 3: Deterministic Scorecard And Version Metadata

- Files/modules:
  - `tests/chat_eval/scorecard.py`
  - `tests/test_chat_eval_closure.py`
- Behavior change:
  - Generates scorecards with policy/model/provider/dataset/git metadata, area summaries, thresholds, blockers, and case results.
  - Supports strict failure semantics for release gates.
- Data contract impact:
  - JSON artifact contract under caller-selected output path.
- Tests to add/update:
  - Scorecard pass/fail threshold tests.
- Verification command:
  - `.venv/bin/python -m tests.chat_eval.scorecard --output /tmp/chat_eval_scorecard.json --strict`
- Rollback or compatibility note:
  - Test helper only; no runtime rollback.

### Step 4: Optional Live Replay Runner

- Files/modules:
  - `tests/chat_eval/live_runner.py`
  - `tests/test_chat_eval_closure.py`
- Behavior change:
  - Adds bounded replay against `/chat` and `/stream/{run_id}`, including SSE parsing, tool event capture, latency, content, and sanitized errors.
  - Supports live-only Agent, wallet, and chain-id overrides so DockerHost replay can replace synthetic fixture context without editing golden cases.
  - Supports excluding tagged legacy groups from focused live replay without deleting their golden cases.
  - Pins curl transport to HTTP/1.1 for `/chat` and SSE stream requests in DockerHost live replay.
- Data contract impact:
  - JSON report contract under caller-selected output path.
- Tests to add/update:
  - Unit tests for payload building, SSE parsing, filtering, and redaction without network calls.
  - Unit test that both live replay curl paths include `--http1.1`.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_chat_eval_closure.py -q`
- Rollback or compatibility note:
  - Optional CLI; local tests do not call network.

### Step 5: Online Sample Ingestion

- Files/modules:
  - `tests/chat_eval/sample_ingestion.py`
  - `tests/test_chat_eval_closure.py`
- Behavior change:
  - Converts sanitized bad-answer samples into reviewable candidate golden cases.
  - Redacts wallet addresses, bearer tokens, API keys, private keys, and long trace-like identifiers.
- Data contract impact:
  - JSONL input/output helper only.
- Tests to add/update:
  - Sanitization and candidate case tests.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_chat_eval_closure.py -q`
- Rollback or compatibility note:
  - Helper-only rollback.

### Step 6: Make Targets And Release Gate

- Files/modules:
  - `Makefile`
  - `scripts/verify_release.sh`
  - `tests/test_chat_eval_closure.py`
- Behavior change:
  - Adds `chat-eval`, `chat-eval-report`, and `chat-eval-live` targets.
  - Adds explicit `chat_behavior_eval` and `chat_eval_scorecard` checks to release verification.
- Data contract impact:
  - Release artifacts include `chat_eval_scorecard.json`.
- Tests to add/update:
  - Static tests for Makefile and release hook wiring.
- Verification command:
  - `AI_BOUNDARY_APPROVED=1 PYTHON=.venv/bin/python scripts/verify_release.sh`
- Rollback or compatibility note:
  - Remove targets and release checks if reverted.

## Risk Controls

- Public contract risks:
  - No public route changes.
- Money/accounting/security risks:
  - Fixture and sample validators must reject/sanitize real secrets and wallet-like identifiers.
  - Live replay does not perform wallet or trading operations.
- Migration/rebuild risks:
  - None.
- Performance risks:
  - Deterministic eval is local and bounded.
  - Live replay is explicit and filterable.
- Deployment/test-branch risks:
  - `verify_release.sh` remains the authority and live replay stays advisory.
- Unrelated local changes to avoid:
  - Do not stage `.artifacts/`, `__pycache__`, private env files, or unrelated runtime edits.

## Completion Criteria

- Spec and plan exist and declare `Workflow Class: HARNESS-SPEC-FIRST-FEATURE`.
- Coverage contract and rubric validate.
- Expanded golden cases pass deterministic eval.
- Scorecard strict mode passes.
- Live runner and sample ingestion unit tests pass.
- Make/release wiring is tested.
- Focused tests pass.
- `AI_BOUNDARY_APPROVED=1 PYTHON=.venv/bin/python scripts/verify_release.sh` passes.
- Code review finds no unresolved issue.
