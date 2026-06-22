# 2026-06-17 RAG Retrieval Eval Specification

## Context

- Spec ID: `SPEC-RAG-EVAL-001`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Related specification:
  - `SPEC-RAG-INFRA-001`: lightweight RAG infrastructure and Gemini embedding provider.
- PRD/source request:
  - Add a mature, lightweight RAG semantic retrieval evaluation component instead of building an eval framework from scratch.
  - Prefer a tool that can run locally and in CI without forcing LangChain, LlamaIndex, or a full RAG platform.
  - Convert the public MOSS GitBook Wiki into reviewed Golden Queries before the Wiki is ingested into a persistent RAG store.
- Target baseline:
  - `main` after lightweight RAG infrastructure and Gemini embedding provider support.
- Current behavior:
  - Unit tests validate RAG plumbing, timeout/degradation behavior, vector-store contracts, and Gemini request/response parsing.
  - Smoke tests validate that ingestion/query paths can run, but do not measure semantic retrieval quality.
  - There is no golden-query dataset, repeatable retrieval-quality metric, or eval artifact that says whether a query retrieved the expected document/chunk.
- Problem:
  - RAG can functionally run while semantic recall silently regresses after changing embedding model, chunk size, score threshold, top_k, or corpus content.
  - Current tests prove "can retrieve", not "retrieves the right evidence".
- Non-goals:
  - No answer-generation or LLM-judge eval in phase 1.
  - No Ragas, DeepEval, TruLens, Phoenix, or observability platform integration in phase 1.
  - No automatic synthetic testset generation in phase 1.
  - No production dataset export or private-document eval corpus in repository.
  - No CI dependency lockfile for Node packages in this Python-first repository.

## Product Semantics

- User/operator workflow:
  - Engineers maintain a small, non-sensitive RAG eval corpus and golden-query set.
  - Promptfoo runs a Python provider that calls this repository's RAG retrieval code.
  - Each golden query asserts that expected documents/chunks appear in the top-k retrieval results.
  - Eval failures block release-quality changes to RAG embedding, chunking, vector search, scoring, or retrieval configuration.
  - Default baseline eval remains deterministic and zero-secret; reviewed MOSS Wiki eval is a separate semantic screening suite intended to run with Gemini embeddings after the network/key environment is ready.
- State model:
  - Eval case:
    - `id`: stable case id.
    - `query`: user-like question.
    - `relevant_doc_ids`: accepted source document ids.
    - `max_rank`: highest rank that counts as pass.
    - `tags`: topic and language labels for debugging.
  - Eval output:
    - `degraded`: whether RAG retrieval degraded.
    - `hits`: ranked list with `doc_id`, score, source metadata, and short preview only.
- Ownership and identity rules:
  - Eval corpus is synthetic or sanitized. It must not contain private customer data, secrets, provider keys, raw production conversations, or sensitive internal documents.
- Permissions/authentication:
  - The first phase runs against local in-process retrieval and does not require an authenticated API server.
  - Future API-backed evals must use local test credentials, never production user tokens.
- Empty, error, retry, timeout, duplicate, and partial-failure behavior:
  - Missing or malformed eval data fails fast.
  - Retrieval degradation fails the affected eval case.
  - Promptfoo CLI absence or npm network failure is reported as a verification blocker, not hidden as a passing eval.
  - Default eval uses `hash` embeddings for zero-secret deterministic CI; sourced local environment may override to `gemini` for live semantic smoke.
  - MOSS semantic eval explicitly uses `gemini`; if Gemini rejects the current caller IP or the local key is unavailable, the run is reported as an external verification blocker while fixture/review tests remain valid.
- Compatibility and migration expectations:
  - Existing pytest and release gates remain valid.
  - Promptfoo is invoked through `npx promptfoo@latest`; no package lock is added in phase 1.

## API / Interface Contract

- Routes, commands, events, jobs, or UI surfaces:
  - Baseline Promptfoo config: `tests/rag_eval/promptfooconfig.yaml`
  - MOSS semantic Promptfoo config: `tests/rag_eval/moss_promptfooconfig.yaml`
  - Python provider: `tests/rag_eval/provider.py`
  - Python assertion: `tests/rag_eval/assert_retrieval.py`
  - Baseline test generator: `tests/rag_eval/test_cases.py`
  - MOSS test generator: `tests/rag_eval/moss_test_cases.py`
  - Baseline corpus: `tests/rag_eval/corpus.jsonl`
  - Baseline Golden Queries: `tests/rag_eval/golden_queries.jsonl`
  - MOSS corpus summaries: `tests/rag_eval/moss_corpus.jsonl`
  - MOSS Golden Queries: `tests/rag_eval/moss_golden_queries.jsonl`
  - MOSS query review evidence: `tests/rag_eval/moss_golden_query_review.jsonl`
  - MOSS coverage contract: `tests/rag_eval/moss_coverage_contract.json`
  - MOSS acceptance evidence contract: `tests/rag_eval/moss_acceptance_evidence_contract.json`
  - MOSS acceptance validator: `tests/rag_eval/moss_acceptance_validator.py`
  - MOSS acceptance status report: `tests/rag_eval/moss_acceptance_status.py`
  - MOSS Golden Query audit report: `tests/rag_eval/moss_golden_query_audit.py`
  - MOSS Gemini preflight: `tests/rag_eval/moss_gemini_preflight.py`
  - MOSS RAG seed manifest: `tests/rag_eval/moss_rag_seed_manifest.json`
  - MOSS RAG import payload generator: `tests/rag_eval/moss_import_payloads.py`
  - MOSS human-readable review: `docs/MOSS_GOLDEN_QUERIES_REVIEW.md`
  - MOSS RAG ingestion runbook: `docs/MOSS_RAG_INGESTION_RUNBOOK.md`
  - Recommended baseline command:
    - `PROMPTFOO_PYTHON=.venv/bin/python npx --yes promptfoo@latest eval -c tests/rag_eval/promptfooconfig.yaml --no-cache --output .artifacts/release/rag_promptfoo_eval.json`
  - Recommended MOSS semantic command, after sourcing local Gemini secret environment and using an allowed caller IP:
    - `PROMPTFOO_PYTHON=.venv/bin/python npx --yes promptfoo@latest eval -c tests/rag_eval/moss_promptfooconfig.yaml --no-cache --output .artifacts/release/moss_rag_promptfoo_eval.json`
- Request fields and validation:
  - Corpus rows must contain `id`, `text`, and optional `meta`.
  - Golden-query rows must contain `id`, `query`, `relevant_doc_ids`, and optional `max_rank`, `top_k`, `tags`.
  - MOSS review rows must contain `id`, `expected_doc_ids`, `challenge_type`, `source_evidence`, and `review_reason`.
  - MOSS coverage contract must contain `contract_id`, minimum counts, required tags/challenge types, and capability-group query ids.
  - MOSS acceptance evidence contract must contain required Promptfoo artifacts, Gemini preflight artifact, pass rates, ingestion counts, smoke-query expectations, and release-gate command.
  - MOSS acceptance validator must fail when required semantic eval, ingestion, smoke, or release artifacts are missing or below contract.
  - MOSS acceptance status report may summarize validator blockers, artifact presence, Gemini preflight state, and next commands, but it is not a substitute for the acceptance validator.
  - MOSS Golden Query audit report must summarize reviewed query counts, corpus counts, source-evidence coverage, source URL and line-range provenance, coverage-contract gaps, and screening-value metrics without storing secrets or full private data.
  - MOSS Gemini preflight must write a redacted artifact with status, HTTP status, embedding model, embedding dimension on success, and blocked reasons such as `API_KEY_IP_ADDRESS_BLOCKED` without writing provider secrets.
  - MOSS RAG seed manifest must pin source fixture paths, row counts, SHA-256 checksums, target knowledge-base metadata, and Gemini embedding target.
  - MOSS import payload generator must produce one `RAGDocumentCreate`-compatible payload per MOSS corpus row.
- Response/envelope fields and types:
  - Provider output is a JSON string with `query`, `degraded`, `reason`, `top_k`, and `hits`.
  - Each hit contains `rank`, `doc_id`, `score`, `source`, and `preview`.
- Status/error codes:
  - Not applicable; first phase is CLI/local provider only.
- Pagination/sorting/filtering:
  - Retrieval results are ranked by the existing vector-store order.
- Backward compatibility:
  - Existing RAG tests and APIs are unchanged.
  - The eval harness uses public in-repo retrieval interfaces and does not bypass RAG service semantics.

## Data / Schema / Projection Impact

- Tables, indexes, migrations, backfills:
  - None.
- Read models, projections, snapshots, caches:
  - None.
- Rebuild or cleanup operators:
  - None.
- Historical data behavior:
  - None.
- Performance-sensitive queries or write paths:
  - Eval should record latency through Promptfoo output artifacts, but phase 1 gates primarily on retrieval correctness.

## Architecture

- Modules/files expected to change:
  - `tests/rag_eval/*`
  - focused pytest contract tests under `tests/`
  - `docs/specifications/*`
  - `docs/implementation-plans/*`
- Data flow:
  1. Promptfoo loads generated baseline test cases from `test_cases.py` or MOSS semantic test cases from `moss_test_cases.py`.
  2. For each query, Promptfoo calls `provider.py:call_api`.
  3. Provider loads corpus once per worker, builds `RAGRetriever`, ingests corpus, and executes retrieval.
  4. Provider returns ranked retrieval output as JSON.
  5. `assert_retrieval.py` checks whether expected documents appear within `max_rank`.
  6. Promptfoo writes a machine-readable artifact when `--output` is used.
- Transaction/concurrency boundaries:
  - No Postgres transaction is used in phase-1 eval.
  - Provider process may cache the in-memory retriever to avoid re-ingesting corpus per test case.
- Observability/logging/metrics:
  - Promptfoo output artifact is the primary eval evidence.
  - Provider output must not include full corpus, full embeddings, provider secrets, or raw private data.
  - Reviewed Wiki-derived Golden Queries must be traceable to source URLs and line ranges so reviewers can audit why a query is included and what evidence it should retrieve.
- Rollback strategy:
  - Remove or disable Promptfoo eval config without changing RAG runtime.
  - Existing pytest-based functional coverage remains available.

## Harness Classification

- Expected gate(s):
  - `HARNESS-SPEC-FIRST-FEATURE`
  - `spec_contract`
  - `harness_workflows`
  - focused pytest contract tests
  - Promptfoo retrieval eval when Node/npm network is available
  - full release verification
- Performance-sensitive class:
  - Eval itself is not production performance-sensitive.
  - RAG retrieval quality is release-sensitive.
- Whether harness mapping must be extended:
  - No new workflow class is required.
- Required performance evidence:
  - None for phase 1 beyond recording Promptfoo artifact.
- Focused verification commands:
  - `.venv/bin/python -m pytest tests/test_rag_promptfoo_eval.py -q`
  - `PROMPTFOO_PYTHON=.venv/bin/python npx --yes promptfoo@latest eval -c tests/rag_eval/promptfooconfig.yaml --no-cache --output .artifacts/release/rag_promptfoo_eval.json`
  - Optional semantic verification after Gemini access is available:
    - `PROMPTFOO_PYTHON=.venv/bin/python npx --yes promptfoo@latest eval -c tests/rag_eval/moss_promptfooconfig.yaml --no-cache --output .artifacts/release/moss_rag_promptfoo_eval.json`
- Prerelease-grade verification commands:
  - `git diff --check`
  - `.venv/bin/python -m pytest -q`
  - `make verify-release`

## Acceptance Criteria

- Functional:
  - `SPEC-RAG-EVAL-001`: Promptfoo can load generated RAG retrieval eval cases.
  - `SPEC-RAG-EVAL-001`: Python provider calls the repository's RAG retriever and returns ranked JSON hits.
  - `SPEC-RAG-EVAL-001`: Python assertion fails degraded retrieval and fails when expected documents are not in `max_rank`.
  - `SPEC-RAG-EVAL-001`: Eval corpus and golden-query files contain at least three sanitized baseline cases.
  - `SPEC-RAG-EVAL-001`: MOSS semantic suite is isolated from the hash baseline so semantic-heavy Wiki cases do not create false failures in zero-secret CI.
  - `SPEC-RAG-EVAL-001`: MOSS Wiki Golden Queries have review evidence mapping each query to expected documents, source line ranges, challenge type, and selection rationale.
  - `SPEC-RAG-EVAL-001`: MOSS Wiki Golden Queries satisfy the `SPEC-RAG-EVAL-001-MOSS-COVERAGE` screening contract.
  - `SPEC-RAG-EVAL-001`: Final completion evidence must satisfy the `SPEC-RAG-EVAL-001-MOSS-ACCEPTANCE-EVIDENCE` contract.
  - `SPEC-RAG-EVAL-001`: MOSS acceptance validator checks the final completion evidence contract.
  - `SPEC-RAG-EVAL-001`: MOSS acceptance status report produces a redacted, non-authoritative handoff artifact for incomplete or blocked runs.
  - `SPEC-RAG-EVAL-001`: MOSS Golden Query audit report produces a machine-readable proof that reviewed queries satisfy the coverage contract, every query has source evidence, corpus rows carry source URLs and line ranges, and review source URLs map back to corpus sources.
  - `SPEC-RAG-EVAL-001`: MOSS Gemini preflight produces a redacted artifact and acceptance validation requires status `passed` before final completion.
  - `SPEC-RAG-EVAL-001`: Human-readable MOSS review documentation lists every MOSS Golden Query id and explains why the set is useful for screening retrieval quality.
  - `SPEC-RAG-EVAL-001`: MOSS RAG seed manifest matches reviewed fixture hashes and can be loaded by local `RAGRetriever.ingest()` without external provider access.
  - `SPEC-RAG-EVAL-001`: MOSS import payload generator outputs one schema-valid `/rag/documents` request body per reviewed corpus row.
  - `SPEC-RAG-EVAL-001`: MOSS RAG ingestion runbook maps the seed manifest into the existing `/rag/knowledge-bases`, `/rag/documents`, `/rag/ingestion-jobs/{job_id}`, and `/rag/query` API flow.
- Edge cases:
  - Missing corpus path fails fast.
  - Invalid provider output fails the assertion.
  - Empty hit list fails for non-empty relevant documents.
- Compatibility:
  - Existing tests and release gate continue to pass.
  - Default eval path needs no provider secret.
  - Live Gemini eval can run after sourcing local secret environment.
- Operational:
  - No secrets, private docs, full embeddings, or production data are committed.
  - Promptfoo network/npm failure is reported explicitly.
- Evidence artifacts:
  - `.artifacts/release/rag_promptfoo_eval.json` when Promptfoo is available.
  - `.artifacts/release/moss_golden_query_audit.json` after the reviewed Golden Query audit runs.
  - `.artifacts/release/moss_rag_acceptance_status.json` when a current status handoff is needed.
  - `.artifacts/release/moss_gemini_preflight.json` after Gemini embedding preflight runs.
  - `.artifacts/release/moss_rag_promptfoo_eval.json` after Gemini semantic eval can reach the provider.

## Review Notes

- Open questions:
  - Whether to add Promptfoo to CI as an always-on gate or keep it as a release/checklist command until npm availability is stable.
- Accepted assumptions:
  - Promptfoo is the selected first-phase eval harness because it supports Python providers and RAG eval workflows while keeping this repository Python-first.
  - Retrieval-only eval is the correct first gate before adding LLM-judge answer evals.
  - MOSS Wiki content committed to eval fixtures should be concise, source-backed summaries rather than full-page copies.
- Rejected alternatives:
  - Ragas and DeepEval are deferred because phase 1 needs deterministic retrieval regression more than answer-level LLM judging.
  - Building a custom full eval framework is rejected; only thin adapters around Promptfoo are allowed.
- Reviewer findings and resolution:
  - Implementation self-review found no blocking defects after separating deterministic baseline eval from the MOSS Gemini semantic suite.
  - Residual verification gap: MOSS semantic Promptfoo run still requires Gemini API access from an allowed caller IP.
