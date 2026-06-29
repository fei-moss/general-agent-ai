# 2026-06-17 RAG Retrieval Eval Implementation Plan

## Plan Header

- Specification: `docs/specifications/2026-06-17-rag-retrieval-eval-specification.md`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Target branch/baseline: `main` after lightweight RAG infrastructure and Gemini embedding provider support.
- Scope summary: Add a lightweight Promptfoo-based retrieval-only RAG eval harness with sanitized corpus, golden queries, Python provider/assertion adapters, focused pytest coverage, and documented verification command.
- Extended scope: add reviewed MOSS GitBook-derived corpus entries and Golden Queries with source-evidence mapping before persistent RAG ingestion.
- Out of scope:
  - Answer-level LLM judge evals.
  - Ragas/DeepEval/TruLens/Phoenix integration.
  - API-server-backed eval runs.
  - Production data export.
  - Node package lockfile or permanent npm dependency.

## Change Steps

### Step 1: Add Retrieval Eval Fixtures

- Files/modules:
  - `tests/rag_eval/corpus.jsonl`
  - `tests/rag_eval/golden_queries.jsonl`
  - `tests/rag_eval/moss_corpus.jsonl`
  - `tests/rag_eval/moss_golden_queries.jsonl`
  - `tests/rag_eval/moss_golden_query_review.jsonl`
  - `tests/rag_eval/moss_coverage_contract.json`
  - `tests/rag_eval/moss_acceptance_evidence_contract.json`
  - `tests/rag_eval/moss_acceptance_validator.py`
  - `tests/rag_eval/moss_acceptance_status.py`
  - `tests/rag_eval/moss_golden_query_audit.py`
  - `tests/rag_eval/moss_gemini_preflight.py`
  - `tests/rag_eval/moss_rag_seed_manifest.json`
  - `tests/rag_eval/moss_import_payloads.py`
  - `docs/MOSS_GOLDEN_QUERIES_REVIEW.md`
  - `docs/MOSS_RAG_INGESTION_RUNBOOK.md`
- Behavior change:
  - Add a small sanitized corpus with known topics.
  - Add golden queries with expected document ids and max accepted rank.
  - Add MOSS Wiki-derived Golden Queries that cover safety, mode comparison, setup, strategy authoring, troubleshooting, and privacy.
  - Keep MOSS semantic fixtures separate from the default hash baseline to avoid treating semantic-heavy cases as deterministic hash-gate failures.
  - Add auditable review evidence for every MOSS Golden Query.
  - Add a machine-readable coverage contract for minimum screening value.
  - Add a machine-readable acceptance evidence contract for final completion.
  - Add an acceptance validator that fails when final evidence artifacts are missing or below contract.
  - Add a non-authoritative acceptance status report command for blocked/incomplete handoff.
  - Add a Golden Query audit command that proves reviewed query counts, source-evidence coverage, source URL/line-range provenance, coverage-contract satisfaction, and screening-value metrics.
  - Add a Gemini embedding preflight command that writes a redacted artifact and classifies external blockers such as `API_KEY_IP_ADDRESS_BLOCKED`.
  - Add a RAG seed manifest that pins reviewed files by path, row count, and SHA-256 for later persistent ingestion.
  - Add a deterministic payload generator for future `/rag/documents` import requests.
  - Add a human-readable review summary for product and engineering review.
  - Add an ingestion runbook that maps the seed manifest to the existing `/rag/*` API and semantic eval acceptance flow.
- Data contract impact:
  - Eval fixture schema becomes stable for Promptfoo provider and test generator.
- Tests to add/update:
  - Focused contract tests verify fixture shape.
  - Focused tests verify every `moss_*` Golden Query has review evidence and source lines.
  - Focused tests verify MOSS query expected document ids exist in the MOSS corpus.
  - Focused tests verify query tags, challenge types, multi-source cases, and capability groups satisfy the coverage contract.
  - Focused tests verify acceptance evidence expectations match baseline eval, MOSS semantic eval, seed manifest, smoke query, and release gate.
  - Focused tests verify the acceptance validator accepts complete synthetic evidence and rejects missing semantic evidence.
  - Focused tests verify the acceptance status report summarizes blockers without leaking provider secrets.
  - Focused tests verify the Golden Query audit report satisfies the coverage contract, proves every query has review evidence, and validates source URL/line-range provenance.
  - Focused tests verify Gemini preflight output is redacted and that blocked preflight status prevents acceptance.
  - Focused tests verify the seed manifest matches fixture checksums and can be loaded by local in-memory `RAGRetriever.ingest()`.
  - Focused tests verify generated import payloads validate against `RAGDocumentCreate`.
  - Focused tests verify the review document references every MOSS Golden Query id.
  - Focused tests verify the ingestion runbook references the seed manifest, API routes, and semantic eval artifact.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_rag_promptfoo_eval.py -q`
- Rollback or compatibility note:
  - Fixtures are test-only and do not affect runtime.

### Step 2: Add Promptfoo Python Provider And Assertion

- Files/modules:
  - `tests/rag_eval/provider.py`
  - `tests/rag_eval/assert_retrieval.py`
  - `tests/rag_eval/test_cases.py`
  - `tests/rag_eval/moss_test_cases.py`
- Behavior change:
  - Provider loads the eval corpus, builds an in-memory `RAGRetriever`, runs top-k retrieval, and returns ranked JSON.
  - Assertion validates degraded state, malformed output, and expected document rank.
  - Test generator converts golden query rows into Promptfoo test cases.
  - MOSS test generator converts reviewed MOSS Golden Queries into Promptfoo cases without changing the baseline generator.
- Data contract impact:
  - Provider output JSON includes `query`, `degraded`, `reason`, `top_k`, and `hits`.
- Tests to add/update:
  - Unit tests directly exercise provider, assertion, and test generation without invoking Promptfoo.
- Verification command:
  - `.venv/bin/python -m pytest tests/test_rag_promptfoo_eval.py -q`
- Rollback or compatibility note:
  - Promptfoo adapters can be removed without runtime impact.

### Step 3: Add Promptfoo Config

- Files/modules:
  - `tests/rag_eval/promptfooconfig.yaml`
  - `tests/rag_eval/moss_promptfooconfig.yaml`
- Behavior change:
  - Define the Promptfoo eval, Python provider, generated tests, and Python assertion.
  - Default provider config uses `hash` embedding for zero-secret local/CI runs; environment variables can override to Gemini.
  - Define a separate MOSS Promptfoo eval that points at `moss_corpus.jsonl`, `moss_test_cases.py`, and Gemini embeddings.
- Data contract impact:
  - Promptfoo output artifact is expected at `.artifacts/release/rag_promptfoo_eval.json` when the documented command runs.
  - MOSS semantic output artifact is expected at `.artifacts/release/moss_rag_promptfoo_eval.json` once Gemini access is available.
- Tests to add/update:
  - Focused tests check both configs reference existing adapter and fixture files.
- Verification command:
  - `PROMPTFOO_PYTHON=.venv/bin/python npx --yes promptfoo@latest eval -c tests/rag_eval/promptfooconfig.yaml --no-cache --output .artifacts/release/rag_promptfoo_eval.json`
  - Optional after Gemini network/key environment is available:
    - `PROMPTFOO_PYTHON=.venv/bin/python npx --yes promptfoo@latest eval -c tests/rag_eval/moss_promptfooconfig.yaml --no-cache --output .artifacts/release/moss_rag_promptfoo_eval.json`
- Rollback or compatibility note:
  - If npm is unavailable, pytest coverage remains valid and Promptfoo failure is reported as an external verification blocker.

### Step 4: Run Harness And Release Verification

- Files/modules:
  - no additional code.
- Behavior change:
  - None.
- Data contract impact:
  - None.
- Tests to add/update:
  - None beyond prior steps.
- Verification command:
  - `git diff --check`
  - `.venv/bin/python -m pytest tests/test_rag_promptfoo_eval.py -q`
  - `.venv/bin/python -m pytest -q`
  - `make verify-release`
- Rollback or compatibility note:
  - No runtime rollback needed.

## Risk Controls

- Public contract risks:
  - None; no API/runtime behavior changes.
- Money/accounting/security risks:
  - No real provider key is committed. Provider output redacts by construction and never emits full embeddings.
- Migration/rebuild risks:
  - None.
- Performance risks:
  - Promptfoo eval can be slower with Gemini; default hash mode keeps local verification cheap.
- Deployment/test-branch risks:
  - Promptfoo depends on npm/network availability unless already cached.
- Unrelated local changes to avoid:
  - Do not stage `.artifacts/`, npm caches, or provider-secret files.

## Completion Criteria

- `SPEC-RAG-EVAL-001` matches implementation.
- Promptfoo config, Python provider, assertion, corpus, and golden query files exist.
- MOSS semantic config, corpus, Golden Queries, case generator, and review evidence files exist.
- MOSS coverage contract exists and is enforced by focused tests.
- MOSS acceptance evidence contract exists and is enforced by focused tests.
- MOSS acceptance validator exists and is covered by focused tests.
- MOSS acceptance status command exists and writes `.artifacts/release/moss_rag_acceptance_status.json` for blocked/incomplete handoff.
- MOSS Golden Query audit command exists and writes `.artifacts/release/moss_golden_query_audit.json` for reviewed-query evidence.
- MOSS Gemini preflight command exists, writes `.artifacts/release/moss_gemini_preflight.json`, and is required by acceptance validation.
- MOSS RAG seed manifest exists, pins reviewed fixture checksums, and passes local ingest smoke.
- MOSS import payload generator exists and produces schema-valid `/rag/documents` payloads.
- MOSS RAG ingestion runbook exists and is tied to the seed manifest plus existing RAG API flow.
- Focused pytest coverage passes.
- Promptfoo eval either passes or reports an external npm/network blocker.
- MOSS semantic eval either passes after Gemini access is available or reports the current Gemini external network/IP blocker.
- Full pytest and release verification pass.
