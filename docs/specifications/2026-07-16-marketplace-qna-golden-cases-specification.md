# 2026-07-16 Marketplace QnA Golden Cases Specification

## Context

- Spec ID: `SPEC-RAG-EVAL-002`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Related authority:
  - `SPEC-RAG-EVAL-001`: existing Promptfoo retrieval evaluation contract.
  - `SPEC-RAG-INFRA-001`: persistent pgvector ingestion and Gemini embedding contract.
- Source bundle:
  - 9 Chinese Markdown files under `Marketplace QnA - CN`.
  - 9 English Markdown files under `Marketplace QnA - EN`.
  - 57 reviewed questions per language, 114 questions total.
- User authorization:
  - The source documents may be committed to this repository as non-sensitive product material.
  - The DockerHost test knowledge base may be configured, populated, and evaluated end to end.
- Pre-V2 rollback baseline:
  - Environment: `chris-general-agent-ai-chat-prod`.
  - Knowledge base: `kb_f7fc8efd685c40e4b309cc42acc618ee`.
  - 18 documents are `EMBEDDED`; 18 ingestion jobs are `SUCCEEDED`; 141 chunks use `gemini-embedding-2`, dimension 256, index version `v1`.
- V2 candidate:
  - Manifest: `marketplace-qna-rag-seed-v2`; source set: `marketplace-qna-bilingual-2026-07-16-v2`.
  - Knowledge base: `kb_d7a8e9ba87f94ad4bb8e0f8466859b39`.
  - 18 documents are `EMBEDDED`; 18 ingestion jobs are `SUCCEEDED`; 143 chunks use `gemini-embedding-2`, dimension 256, index version `v1`.

## Goal

Create a reproducible bilingual Golden Case suite that proves the Marketplace QnA corpus is complete, semantically retrievable, and usable through the configured chat path. The suite must be strong enough to detect regressions in source content, chunking, embeddings, ranking, language handling, or default knowledge-base binding.

## Product Semantics

- Every source question is represented by one semantic Golden Case in the same language.
- Golden queries must be natural paraphrases, not copies of the source question, so passing results demonstrate semantic retrieval rather than string overlap.
- Each case maps to one expected source document and an auditable source line range.
- Retrieval passes only when the expected document appears within the first five results and the request is not degraded.
- One representative question per source document also runs through the real chat path after the default knowledge base is bound.
- Source claims are treated as the product-content contract. This suite checks faithful retrieval and answer grounding; it does not independently verify external legal, financial, or protocol claims.

## Repository Artifacts

The implementation adds one isolated Marketplace QnA fixture family under `tests/rag_eval/`:

- `marketplace_qna_sources/zh-CN/*.md` and `marketplace_qna_sources/en/*.md`: the 18 authorized source files.
- `marketplace_qna_corpus.jsonl`: 18 source rows matching the production document boundary.
- `marketplace_qna_golden_queries.jsonl`: 114 paraphrased semantic queries.
- `marketplace_qna_golden_query_review.jsonl`: expected documents, original questions, source line ranges, challenge types, and review rationale.
- `marketplace_qna_coverage_contract.json`: minimum counts and required topic/language/source coverage.
- `marketplace_qna_rag_seed_manifest.json`: source paths, hashes, row counts, knowledge-base metadata, and embedding target.
- `marketplace_qna_acceptance_evidence_contract.json`: machine-readable completion thresholds.
- `marketplace_qna_test_cases.py`: Promptfoo test-case generator.
- `marketplace_qna_import_payloads.py`: deterministic `/rag/documents` payload generator.
- `marketplace_qna_golden_query_audit.py`: fixture and coverage audit.
- `marketplace_qna_live_eval.py`: authenticated DockerHost retrieval evaluation without persisting credentials.
- `marketplace_qna_acceptance_validator.py`: final evidence validator.
- `marketplace_qna_promptfooconfig.yaml`: local Gemini semantic retrieval configuration.
- `docs/MARKETPLACE_QNA_GOLDEN_CASES_REVIEW.md`: human review and execution guide.
- `docs/MARKETPLACE_QNA_RAG_INGESTION_RUNBOOK.md`: repeatable import and rollback-safe verification flow.

Existing generic provider/assertion code should be reused where possible. Marketplace-specific code may adapt the fixture paths and live API envelope but must not duplicate the RAG runtime.

## Data Contracts

### Corpus Row

Each JSONL row contains:

- `id`: stable document id, `marketplace_qna_<language>_<order>`.
- `text`: exact Markdown source content.
- `meta.language`: `zh-CN` or `en`.
- `meta.source_file`: original filename.
- `meta.source_uri`: stable `urn:moss:marketplace-qna:<language-key>:<order>`.
- `meta.source_sha256`: exact source-file hash.
- `meta.document_order`: 1 through 9.
- `meta.source_lines`: full source line range.

### Golden Query Row

Each JSONL row contains:

- `id`: stable language-scoped case id.
- `query`: reviewed semantic paraphrase.
- `relevant_doc_ids`: exactly one expected corpus document id.
- `max_rank`: 5.
- `top_k`: 5.
- `tags`: language, topic, challenge type, and source order.

### Review Row

Each review row contains:

- `id`: matching Golden Query id.
- `expected_doc_ids`: matching expected document ids.
- `original_question`: exact source question.
- `source_evidence`: source path, line range, and answer claim summary.
- `challenge_type`: direct fact, comparison, process, calculation, safety, limitation, or future-status retrieval.
- `review_reason`: why the paraphrase is semantically equivalent and useful for screening.

## Coverage Contract

The suite must prove:

- 18 source documents total: 9 Chinese and 9 English.
- 114 Golden Cases total: 57 Chinese and 57 English.
- Every source question has exactly one Golden Case.
- Every Golden Case has exactly one review row and one non-empty source-evidence entry.
- Every source document has at least one Golden Case.
- All nine topic groups are represented in both languages:
  - Marketplace definition.
  - Agent Tool.
  - Agent types.
  - Owning and Minting.
  - Discover.
  - Launching and Fundraising.
  - DEX and secondary market.
  - Security and risk.
  - Ecosystem and future.
- Safety, risk, fee, redemption, ownership, strategy-change, and platform-limitation claims are explicitly covered.

## Acceptance Criteria

### Fixture and Review Gates

- All source hashes match the seed manifest.
- Corpus, Golden Query, review, and coverage identifiers are unique and mutually consistent.
- Source line ranges resolve to the question and answer represented by the case.
- Focused pytest contract tests pass.

### Semantic Retrieval Gate

- Gemini preflight returns a finite 256-dimensional vector.
- Promptfoo completes all 114 cases.
- 114 of 114 cases pass the expected-document-in-top-five assertion.
- No case returns `degraded=true`.
- All 18 source documents appear as expected documents in passing cases.
- Top-1 expected-document accuracy is reported and must be at least 80 percent.

### Live DockerHost Gate

- Live evaluation targets the configured knowledge base and reads the administrator identity from the local Keychain or an environment variable; the identity must never be written to artifacts.
- All 114 live `/rag/query` calls return HTTP 200 and `degraded=false`.
- All live cases pass expected source URI plus language matching within the first five results.
- One representative chat case per source document, 18 total, reaches a terminal succeeded state.
- Each chat case produces an answer containing the case's required facts and no forbidden contradictory claim.
- Chat evidence confirms the server-selected default knowledge base; clients do not inject a knowledge-base id.

### Release Gate

- Golden Query audit passes.
- Acceptance validator reports `passed` with no blockers.
- `git diff --check` passes.
- Focused Marketplace QnA tests pass.
- Existing RAG eval tests pass.
- `scripts/verify_release.sh` passes.

## Error and Retry Semantics

- Missing or malformed source files fail before evaluation begins.
- Any hash mismatch fails the fixture gate.
- Any missing review evidence or uncovered source question fails the coverage gate.
- HTTP, provider, timeout, or degraded retrieval errors fail the affected case and remain visible in the artifact.
- Live evaluation may retry transient transport failures with bounded backoff, but semantic misses are never retried into a pass.
- A case may only be changed when source evidence proves the query was ambiguous or mapped incorrectly. Cases must not be weakened merely to raise the score.
- Runtime or API changes discovered as necessary require a specification update and repository approval before editing approval-controlled paths.

## Security and Operations

- The generated RAG administrator id remains in the local macOS Keychain and DockerHost runtime configuration only.
- Provider keys, bearer values, raw embeddings, and private environment output must not enter Git, logs, Promptfoo artifacts, or review documents.
- Source documents are authorized product content and may enter Git; uploaded runtime content remains owner-scoped.
- The DockerHost environment is a test branch-space with bounded lifetime. Acceptance proves the current deployment, not indefinite retention or production-private ingress.

## Rollback

- Repository fixtures and evaluators can be reverted without changing RAG runtime behavior.
- The default knowledge-base binding can be removed by redeploying with empty `RAG_DEFAULT_KNOWLEDGE_BASE_ID` and `RAG_INTERNAL_OWNER_USER_ID` while retaining the persistent data.
- Uploaded documents remain in the managed Postgres volume unless an explicit deletion or environment-destroy operation is authorized.

## Rejected Alternatives

- A 36-case curated suite is rejected because it cannot prove every supplied QnA item is covered.
- Exact source questions are rejected as Golden queries because embedding the same text present in the chunk produces weak screening value.
- An ad hoc live-only evaluator is rejected because it cannot reproduce fixture, review, and coverage failures locally.
- Adding an LLM judge is deferred; deterministic retrieval and required/forbidden fact checks provide a more auditable first acceptance gate.
