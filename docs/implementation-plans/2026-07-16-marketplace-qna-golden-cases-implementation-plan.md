# Marketplace QnA Golden Cases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Commit the authorized bilingual Marketplace QnA corpus, build 114 reviewed semantic Golden Cases plus 18 representative chat cases, and prove local and DockerHost retrieval/chat acceptance.

**Architecture:** Preserve each supplied Markdown file as one corpus document so local evaluation matches production ingestion boundaries. A focused fixture builder parses all 114 QnA blocks and combines them with reviewed paraphrases and fact expectations to generate the corpus, Golden Query, review, manifest, coverage, and chat-case artifacts. Existing Promptfoo provider/assertion code handles local retrieval; Marketplace-specific live and acceptance tools add authenticated DockerHost verification without persisting credentials.

**Tech Stack:** Python 3.12, pytest, Promptfoo Python provider, Gemini Embedding 2, FastAPI `/rag/*`, Celery, PostgreSQL 16 with pgvector 0.8.2, DockerHost `envctl`.

## Global Constraints

- Specification: `docs/specifications/2026-07-16-marketplace-qna-golden-cases-specification.md` (`SPEC-RAG-EVAL-002`).
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE` with final deep verification.
- Exactly 18 source documents, 114 Golden Cases, and 18 chat cases.
- Golden queries are semantic paraphrases, never exact copies of source questions.
- Retrieval acceptance is 114/114 within top five, zero degraded cases, and at least 80 percent top-one accuracy.
- Raw provider keys, RAG administrator values, marketplace identity values, and embeddings never enter Git or artifacts.
- Runtime/API/task/database code is unchanged unless a separately approved spec revision requires it.
- No subagents are used because the active repository instructions require primary-agent execution unless delegation is explicitly requested.

---

### Task 1: Commit Authorized Sources and Define the Fixture Builder Contract

**Files:**
- Create: `tests/rag_eval/marketplace_qna_sources/zh-CN/*.md`
- Create: `tests/rag_eval/marketplace_qna_sources/en/*.md`
- Create: `tests/rag_eval/marketplace_qna_fixture_builder.py`
- Create: `tests/test_marketplace_qna_eval.py`

**Interfaces:**
- Consumes: 18 exact Markdown files authorized by the user.
- Produces: `parse_source(path: Path, spec: SourceSpec) -> ParsedSource`, `build_fixture_bundle() -> FixtureBundle`, and stable ids `marketplace_qna_<lang>_<order>` / `marketplace_qna_<lang>_<order>_<question>`.

- [ ] **Step 1: Copy the 18 exact source files into language-scoped fixture directories**

Use a mechanical copy that preserves bytes, then prove each destination hash equals its source hash:

```bash
mkdir -p tests/rag_eval/marketplace_qna_sources/zh-CN tests/rag_eval/marketplace_qna_sources/en
cp '/Users/chris/Downloads/Marketplace QnA - CN/'*.md tests/rag_eval/marketplace_qna_sources/zh-CN/
cp '/Users/chris/Downloads/Marketplace QnA - EN/'*.md tests/rag_eval/marketplace_qna_sources/en/
```

- [ ] **Step 2: Write failing source-discovery and QnA-count tests**

Add tests that assert:

```python
def test_marketplace_qna_sources_have_expected_shape():
    bundle = build_fixture_bundle()
    assert len(bundle.sources) == 18
    assert sum(source.language == "zh-CN" for source in bundle.sources) == 9
    assert sum(source.language == "en" for source in bundle.sources) == 9
    assert sum(len(source.questions) for source in bundle.sources) == 114
    assert {len(source.questions) for source in bundle.sources if source.order == 4} == {16}
```

- [ ] **Step 3: Run the focused test and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_marketplace_qna_eval.py::test_marketplace_qna_sources_have_expected_shape -q
```

Expected: fail because `marketplace_qna_fixture_builder` does not exist.

- [ ] **Step 4: Implement Markdown parsing and stable ids**

Implement immutable dataclasses for `SourceSpec`, `QuestionBlock`, `ParsedSource`, and `FixtureBundle`. Parse `**Q:` and `**Q：` headings, capture the answer through the next question or EOF, and record one-based `question_line`, `answer_start_line`, and `answer_end_line`. Fail on empty answers, duplicate ids, or counts other than `[5,7,2,16,4,9,4,7,3]` per language.

- [ ] **Step 5: Run focused tests and commit**

Run:

```bash
.venv/bin/python -m pytest tests/test_marketplace_qna_eval.py -q
git diff --check
```

Commit:

```bash
git add tests/rag_eval/marketplace_qna_sources tests/rag_eval/marketplace_qna_fixture_builder.py tests/test_marketplace_qna_eval.py
git commit -m "test: add marketplace qna source fixtures"
```

### Task 2: Add Reviewed Paraphrases, Corpus, Golden Queries, and Review Evidence

**Files:**
- Create: `tests/rag_eval/marketplace_qna_case_definitions.jsonl`
- Create: `tests/rag_eval/marketplace_qna_corpus.jsonl`
- Create: `tests/rag_eval/marketplace_qna_golden_queries.jsonl`
- Create: `tests/rag_eval/marketplace_qna_golden_query_review.jsonl`
- Create: `tests/rag_eval/marketplace_qna_chat_cases.jsonl`
- Modify: `tests/rag_eval/marketplace_qna_fixture_builder.py`
- Modify: `tests/test_marketplace_qna_eval.py`

**Interfaces:**
- Consumes: parsed `QuestionBlock` records from Task 1.
- Produces: `load_case_definitions() -> dict[str, CaseDefinition]` and deterministic JSONL fixture bytes.

- [ ] **Step 1: Write failing semantic-case contract tests**

Assert exactly 114 unique case definitions, 57 per language, no normalized paraphrase equals its original question, every source question id is present, and exactly one representative chat case exists per source document:

```python
assert len(cases) == 114
assert Counter(case.language for case in cases.values()) == {"zh-CN": 57, "en": 57}
assert all(normalize(case.query) != normalize(case.original_question) for case in cases.values())
assert len([case for case in cases.values() if case.representative_chat]) == 18
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_marketplace_qna_eval.py -k 'case or paraphrase or representative' -q
```

Expected: fail because case definitions and generated fixtures do not exist.

- [ ] **Step 3: Author all 114 reviewed case definitions**

Each JSONL row must contain the stable question id, semantic paraphrase, challenge type, concise required facts, forbidden contradictory claims, and `representative_chat`. Use one representative per source document. Required facts are deterministic substrings or normalized alternatives derived from the supplied answer; they must not introduce facts absent from the source.

- [ ] **Step 4: Generate deterministic fixture files**

Extend the builder to emit:

```python
corpus_row = {"id": source.id, "text": source.text, "meta": source.metadata()}
golden_row = {"id": case.id, "query": case.query, "relevant_doc_ids": [case.document_id], "max_rank": 5, "top_k": 5, "tags": case.tags()}
review_row = {"id": case.id, "expected_doc_ids": [case.document_id], "original_question": block.question, "challenge_type": case.challenge_type, "source_evidence": [block.evidence()], "review_reason": case.review_reason()}
```

Write files with UTF-8, one sorted JSON object per line, and `ensure_ascii=False`.

- [ ] **Step 5: Verify determinism and commit**

Run the builder twice and assert no diff, then run focused tests:

```bash
.venv/bin/python -m tests.rag_eval.marketplace_qna_fixture_builder --write
cp tests/rag_eval/marketplace_qna_golden_queries.jsonl /tmp/marketplace-golden-before.jsonl
.venv/bin/python -m tests.rag_eval.marketplace_qna_fixture_builder --write
cmp /tmp/marketplace-golden-before.jsonl tests/rag_eval/marketplace_qna_golden_queries.jsonl
.venv/bin/python -m pytest tests/test_marketplace_qna_eval.py -q
```

Commit all case and generated fixture files with message `test: add marketplace qna golden cases`.

### Task 3: Add Coverage, Seed Manifest, and Import Contracts

**Files:**
- Create: `tests/rag_eval/marketplace_qna_coverage_contract.json`
- Create: `tests/rag_eval/marketplace_qna_rag_seed_manifest.json`
- Create: `tests/rag_eval/marketplace_qna_acceptance_evidence_contract.json`
- Create: `tests/rag_eval/marketplace_qna_import_payloads.py`
- Modify: `tests/test_marketplace_qna_eval.py`

**Interfaces:**
- Consumes: Task 2 corpus, Golden Query, review, and chat-case JSONL.
- Produces: schema-valid `RAGDocumentCreate` payloads and machine-readable minimum acceptance thresholds.

- [ ] **Step 1: Write failing contract tests**

Tests must assert 18/114/18 counts, 9 topic groups per language, all 18 document ids covered, every case linked to review evidence, source checksums matching the committed Markdown files, and payloads accepted by `RAGDocumentCreate`.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_marketplace_qna_eval.py -k 'coverage or manifest or payload or acceptance' -q
```

- [ ] **Step 3: Implement contracts and payload generator**

Set exact thresholds:

```json
{
  "source_documents": 18,
  "golden_queries": 114,
  "chat_cases": 18,
  "promptfoo_required_passes": 114,
  "live_required_passes": 114,
  "minimum_top1_rate": 0.8,
  "maximum_degraded_cases": 0,
  "maximum_failed_ingestion_jobs": 0
}
```

Payload metadata must use the production `source_uri`, language, filename, SHA-256, source set, document order, and corpus version.

- [ ] **Step 4: Run tests and commit**

Run focused tests plus `scripts/check_spec_contract.sh`, then commit with message `test: define marketplace qna acceptance contracts`.

### Task 4: Add Local Promptfoo and Golden Query Audit

**Files:**
- Create: `tests/rag_eval/marketplace_qna_test_cases.py`
- Create: `tests/rag_eval/marketplace_qna_promptfooconfig.yaml`
- Create: `tests/rag_eval/marketplace_qna_golden_query_audit.py`
- Modify: `tests/test_marketplace_qna_eval.py`

**Interfaces:**
- Consumes: generic `generate_tests_from_path`, `provider.py`, `assert_retrieval.py`, and Task 2/3 fixtures.
- Produces: 114 Promptfoo tests and `.artifacts/release/marketplace_qna_golden_query_audit.json`.

- [ ] **Step 1: Write failing test-generator and audit tests**

Assert the test generator returns 114 cases with `max_rank=5`, the config uses Gemini 2 / dimension 256 / chunk size 400 / overlap 80 / top_k 5, and the audit reports full source/question/review/coverage satisfaction.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_marketplace_qna_eval.py -k 'promptfoo or audit' -q
```

- [ ] **Step 3: Implement adapters and audit**

Reuse generic provider/assertion files. The audit output must contain only ids, counts, tags, hashes, source paths, line ranges, and gaps; it must never contain full embeddings or credentials.

- [ ] **Step 4: Run local Gemini semantic eval**

Run:

```bash
source /Users/chris/.codex-local/general-agent-ai/gemini_env.sh
.venv/bin/python -m tests.rag_eval.marketplace_qna_golden_query_audit --output .artifacts/release/marketplace_qna_golden_query_audit.json
PROMPTFOO_PYTHON=.venv/bin/python npx --yes promptfoo@latest eval -c tests/rag_eval/marketplace_qna_promptfooconfig.yaml --no-cache --output .artifacts/release/marketplace_qna_promptfoo_eval.json
```

Expected: 114 successes, 0 failures, 0 errors. Record top-one accuracy separately from provider output.

- [ ] **Step 5: Commit**

Commit adapters, audit, tests, and config with message `test: add marketplace qna semantic eval`.

### Task 5: Add Live DockerHost Retrieval and Chat Evaluation

**Files:**
- Create: `tests/rag_eval/marketplace_qna_live_eval.py`
- Modify: `tests/test_marketplace_qna_eval.py`

**Interfaces:**
- Consumes: base URL, knowledge-base id, administrator id from `RAG_ADMIN_USER_ID` or macOS Keychain, 114 Golden Queries, review metadata, and 18 chat cases.
- Produces: redacted retrieval and chat evidence JSON.

- [ ] **Step 1: Write failing redaction, ranking, and fact-check tests**

Unit tests must cover HTTP retry boundaries, `degraded=true`, expected source/language matching, top-one calculation, required fact alternatives, forbidden facts, terminal chat state, and proof that serialized evidence contains neither the administrator value nor marketplace identity values.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_marketplace_qna_eval.py -k 'live or redact or fact or top1' -q
```

- [ ] **Step 3: Implement retrieval evaluation**

Use stdlib `urllib.request`. Send 114 `POST /rag/query` requests with `strict=true`, `top_k=5`, and no semantic retry. Record case id, HTTP status, degraded flag, matched source URI/language/rank, latency, and pass/fail reason.

- [ ] **Step 4: Implement chat evaluation**

Use test-only valid Marketplace headers (`marketplace:user:<numeric-id>` and a reserved non-production EVM wallet). Send 18 `/chat` requests without client knowledge-base metadata, consume SSE or poll `/runs/{id}` to terminal state, and fetch the assistant answer through the supported conversation/message surface. Record only case id, run ids, terminal status, required/forbidden fact results, RAG tool evidence, and a bounded answer preview.

- [ ] **Step 5: Run live evaluation**

Run:

```bash
.venv/bin/python -m tests.rag_eval.marketplace_qna_live_eval \
  --base-url https://api-chris-general-agent-ai-chat-prod.dkhost.vixmk-yo.org \
  --knowledge-base-id kb_f7fc8efd685c40e4b309cc42acc618ee \
  --keychain-service general-agent-ai-rag-admin-id \
  --retrieval-output .artifacts/release/marketplace_qna_live_retrieval.json \
  --chat-output .artifacts/release/marketplace_qna_live_chat.json
```

Expected: 114/114 retrieval passes, no degraded cases, top-one at least 80 percent, 18/18 chat terminal successes, and 18/18 deterministic fact checks.

- [ ] **Step 6: Commit**

Commit the evaluator and unit tests with message `test: add marketplace qna live acceptance`.

### Task 6: Add Acceptance Validator, Review Documentation, and Runbook

**Files:**
- Create: `tests/rag_eval/marketplace_qna_acceptance_validator.py`
- Create: `tests/rag_eval/marketplace_qna_acceptance_status.py`
- Create: `docs/MARKETPLACE_QNA_GOLDEN_CASES_REVIEW.md`
- Create: `docs/MARKETPLACE_QNA_RAG_INGESTION_RUNBOOK.md`
- Modify: `tests/test_marketplace_qna_eval.py`

**Interfaces:**
- Consumes: fixture audit, ingestion summary, Promptfoo artifact, live retrieval artifact, live chat artifact, and release summary.
- Produces: `.artifacts/release/marketplace_qna_acceptance_status.json` with `status=passed` only when all exact thresholds are met.

- [ ] **Step 1: Write failing validator tests**

Use synthetic complete evidence to prove pass, then independently remove or lower each required artifact/count/rate and prove the validator reports a stable blocker.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_marketplace_qna_eval.py -k 'acceptance_validator or acceptance_status' -q
```

- [ ] **Step 3: Implement validator and documentation**

The review document lists all case ids grouped by topic/language and explains screening value. The runbook contains exact preflight, import, query, Promptfoo, live eval, acceptance, rollback, and secret-hygiene commands.

- [ ] **Step 4: Run focused tests and commit**

Run all Marketplace QnA tests and existing RAG eval tests, then commit with message `docs: add marketplace qna acceptance workflow`.

### Task 7: Final Verification, Deployment, and Completion Audit

**Files:**
- Generated: `.artifacts/release/marketplace_qna_*.json`
- Existing generated: `.artifacts/release/summary.json`

**Interfaces:**
- Consumes: all prior task outputs.
- Produces: final release/online acceptance evidence and a requirement-by-requirement completion table.

- [ ] **Step 1: Run local gates**

```bash
git diff --check
.venv/bin/python -m pytest tests/test_marketplace_qna_eval.py tests/test_rag_promptfoo_eval.py tests/test_rag_api.py tests/test_rag_service.py -q
scripts/check_spec_contract.sh
scripts/check_harness_workflows.sh
scripts/verify_release.sh
```

- [ ] **Step 2: Generate final artifacts**

```bash
.venv/bin/python -m tests.rag_eval.marketplace_qna_acceptance_status \
  --output .artifacts/release/marketplace_qna_acceptance_status.json
.venv/bin/python -m tests.rag_eval.marketplace_qna_acceptance_validator
```

Expected: `status=passed`, no blockers.

- [ ] **Step 3: Commit and push the completed evaluation suite**

Commit any remaining docs/fixtures, then push `codex/zai-glm52-dockerhost`.

- [ ] **Step 4: Redeploy the pushed ref without destructive data operations**

Use `envctl branch-space deploy` with Z.AI, Gemini, RAG admin, default knowledge base, and internal owner supplied through `--secret-env`; do not run `down`, delete the managed volume, or expose Postgres/Redis.

- [ ] **Step 5: Repeat live smoke on the deployed commit**

Verify environment health, commit SHA, 18 documents, 141 chunks, 18 succeeded jobs, 114 live retrieval cases, and 18 chat cases.

- [ ] **Step 6: Completion audit**

Map every requirement in `SPEC-RAG-EVAL-002` to current file, test, artifact, database, or live-runtime evidence. Do not mark complete if any item is absent, stale, indirect, or below threshold.
