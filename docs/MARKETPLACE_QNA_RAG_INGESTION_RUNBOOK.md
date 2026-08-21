# Marketplace QnA RAG Ingestion Runbook

## Purpose

This runbook is the repeatable operator flow for `SPEC-RAG-EVAL-002`. It covers
the 17 Chinese and 17 English Marketplace QnA Markdown files, persistent pgvector
ingestion, local semantic evaluation, live DockerHost retrieval, and live chat
acceptance through the server-owned default knowledge base.

The RAG administrator is an internal runtime identity. Store it in macOS
Keychain or an approved secret manager only; never place it in Git, command
output, release artifacts, or chat metadata.

## Standard Workflow

Complete the persistent import and DockerHost deployment described below, then
run the canonical acceptance entrypoint:

```bash
source /Users/chris/.codex-local/general-agent-ai/gemini_env.sh
: "${MARKETPLACE_QNA_BASE_URL:?export the target API base URL}"
: "${MARKETPLACE_QNA_KNOWLEDGE_BASE_ID:?export the target knowledge-base id}"
make marketplace-qna-acceptance
```

Use the stage targets only to diagnose a failed gate:

```bash
make marketplace-qna-preflight
make marketplace-qna-local
make marketplace-qna-live
make marketplace-qna-final
```

The Make workflow does not upload or deploy. Those actions mutate persistent
or remote state and remain explicit operator steps. The aggregate target checks
all required values and the ingestion summary before any provider-backed work,
then stops at the first failed gate.

## Preconditions

- The project DockerHost adapter validates successfully.
- API, worker, PostgreSQL/pgvector, and Redis are healthy.
- `RAG_ENABLED=true`, `RAG_VECTOR_STORE=pgvector`.
- Embeddings use Gemini `gemini-embedding-2`, and `EMBEDDING_DIM=1536` is
  explicitly present on every deploy. The application runtime default remains
  `256`; never rely on that default for V8.
- The internal administrator is included in `RAG_ADMIN_USER_IDS`.
- `RAG_DEFAULT_KNOWLEDGE_BASE_ID` and `RAG_INTERNAL_OWNER_USER_ID` are set on
  the server; `RAG_ALLOW_CLIENT_KNOWLEDGE_BASE_ID=false`.
- Runtime provider keys are injected with `--secret-env` or `--secret-file`,
  never inline.

## Reviewed Seed

Current manifest: `marketplace-qna-rag-seed-v8`; source set:
`marketplace-qna-bilingual-2026-08-21-v8`.

| Role | Path | Rows |
| --- | --- | ---: |
| Corpus | `tests/rag_eval/marketplace_qna_corpus.jsonl` | 34 |
| Golden queries | `tests/rag_eval/marketplace_qna_golden_queries.jsonl` | 350 |
| Review evidence | `tests/rag_eval/marketplace_qna_golden_query_review.jsonl` | 350 |
| Chat cases | `tests/rag_eval/marketplace_qna_chat_cases.jsonl` | 34 |

The standard preflight validates required values, the ingestion summary,
fixture hashes, Golden Query coverage, and focused contracts:

```bash
make marketplace-qna-preflight
```

The file hashes must match
`tests/rag_eval/marketplace_qna_rag_seed_manifest.json` before upload.

## Persistent Import

1. Read the administrator ID from Keychain into the process environment without
   printing it.
2. Create one internal knowledge base through `POST /rag/knowledge-bases`.
3. Generate the 34 schema-valid request bodies:

```bash
.venv/bin/python -m tests.rag_eval.marketplace_qna_import_payloads \
  --knowledge-base-id <knowledge_base_id>
```

4. Submit every body through `POST /rag/documents` as the RAG administrator.
5. Poll `GET /rag/ingestion-jobs/{job_id}` until every job is terminal.
6. Require 34 `SUCCEEDED`, 0 failed, 34 persisted documents, 313 chunks, and
   equality between uploaded SHA-256 metadata and the source manifest.
7. Save the redacted result as
   `.artifacts/release/marketplace_qna_ingestion_summary.json`.

Repeating the same payload is an idempotency check. It must not create a second
logical document or duplicate chunks.

Intermediate worker failures return the document and job to `PENDING` for the
next bounded Celery attempt; only the exhausted attempt becomes `FAILED`. The
reaper also redispatches stale `PENDING` jobs and stale `RUNNING` jobs left by a
lost worker. Treat a job that remains non-terminal beyond the configured stale
window as a worker/reaper incident rather than submitting a different document.

A terminal `FAILED` import is different. `POST /rag/documents` finds an existing
document by `(knowledge_base_id, content_hash)`, returns its latest job, and
enqueues only when that job is `PENDING`. Resubmitting the same payload therefore
does **not** retry or replace a `FAILED` job, even though chunk writes themselves
use an idempotent upsert. After the dimension migration has succeeded, inspect
the affected V8 knowledge base and delete only its failed document rows before
resubmitting:

```sql
SELECT status, count(*)
FROM rag_document
WHERE knowledge_base_id = '<V8_KNOWLEDGE_BASE_ID>'
GROUP BY status;

DELETE FROM rag_document
WHERE knowledge_base_id = '<V8_KNOWLEDGE_BASE_ID>'
  AND status = 'FAILED'
RETURNING id;
```

For the failed 34-document attempt, require the inspection and `RETURNING` count
to be exactly 34. The `ON DELETE CASCADE` foreign key removes the associated
failed ingestion jobs and any partial chunks; it does not touch the knowledge
base or any retained V6/V7 knowledge base. The next submission then creates new
document and job rows.

## Local Semantic Evaluation

Run Gemini preflight and the 350-case Promptfoo suite with production embedding
and chunk settings:

```bash
make marketplace-qna-local
```

Acceptance requires 350/350 top-5 passes, no degraded cases, and Top-1 at least
80%. Retrieval is filtered to the query language so mirrored Chinese and
English documents do not compete with each other.

The earlier 316-query benchmark (`301/316`, Top-1 `80.4%`) was measured at 256 dimensions.
It is historical V7 evidence, not a V8 acceptance result, and must be re-baselined at 1536 dimensions before V8 promotion.

## Embedding-Dimension Migration

The normal DockerHost deploy must run the fail-closed `migrate` service before
the API or worker starts. Migration
`20260821_001_rag_embedding_dimensionless` drops the fixed-dimension HNSW index
and changes `rag_document_chunk.embedding` from `vector(256)` to dimensionless
`vector`; it preserves all existing 256-dimensional rows. Confirm that the
migration service completed successfully **before** retrying a 1536-dimensional
import. At the current scale of hundreds of chunks per knowledge base,
sequential scan is the accepted retrieval plan; a dimension-typed ANN index is
a future scale follow-up.

Changing the seed contract to 1536 dimensions also requires
`EMBEDDING_DIM=1536` to be explicitly supplied to the server on every deploy
and a full V8 re-ingest into a **new** knowledge base. The runtime setting still
defaults to 256. Do not append 1536-dimensional chunks to a knowledge base
created with a different dimension.

The dimensionless column permits retained knowledge bases to use different
dimensions. Application ingestion and query checks enforce the configured
dimension, and distance queries filter by `knowledge_base_id` before comparing
vectors, so each knowledge base must remain dimension-uniform and vectors from
different knowledge bases never meet in one comparison.

While the server runs with the new dimension, old-dimension knowledge bases are
unreachable for successful retrieval: the query vector and stored chunk vector
dimensions do not match, so requests degrade with an embedding-dimension
mismatch. Promote V8 only by switching `RAG_DEFAULT_KNOWLEDGE_BASE_ID` to the
newly ingested V8 knowledge base after its acceptance gates pass.

## Server Default Knowledge Base

Deploy through the repository release wrapper after pushing the Git ref. It
automatically forwards the complete required runtime environment and rejects
missing values or an accidental mock provider:

```bash
source /Users/chris/.codex-local/dockerhost/envctl_env.sh
.venv/bin/python scripts/dockerhost_release.py deploy \
  --name <environment> \
  --git-url <git-url> \
  --git-ref <pushed-ref> \
  --base-url <api-base-url> \
  --secret-env ZAI_API_KEY \
  --secret-env GEMINI_API_KEY \
  --execute
envctl branch-space status --name <environment>
```

Do not run `down`, recreate the environment, or remove the managed PostgreSQL
volume for a normal corpus refresh.

`branch-space deploy` regenerates the deployment environment from the values
passed to that invocation. Export and pass required non-secret Compose inputs
through `--secret-env` as well as credentials; otherwise omitted values fall
back to Compose defaults (for example `LLM_PROVIDER=mock`). Verify `/readyz`
reports a configured real provider before starting live chat acceptance.

## Live Acceptance

The evaluator reads the admin ID from Keychain by default and generates one
ephemeral Marketplace test identity when chat identity variables are absent.
Raw identities are redacted before evidence is written.

```bash
make marketplace-qna-live
```

The chat payload intentionally contains no `knowledge_base_id`. Every one of
the 34 chat cases must reach `SUCCEEDED`, emit `RETRIEVAL_STARTED` and
`RETRIEVAL_FINISHED`, include all required fact groups, and contain no forbidden
claim.

Run the repository release harness and produce the final acceptance status:

```bash
make marketplace-qna-final
```

## Rollback and Retention

- Dimension rollback is atomic: revert `EMBEDDING_DIM` and
  `RAG_DEFAULT_KNOWLEDGE_BASE_ID` together so the query-vector dimension matches
  the retained knowledge base. The dimensionless schema migration remains in
  place and the retained 256-dimensional chunks need no rewrite. Do not delete
  either knowledge base or the managed PostgreSQL volume.
- Keep the previous knowledge base and both evidence sets until the replacement
  corpus has passed the same contract and its rollback window has closed.
- Branch spaces have platform TTLs. Check and extend the environment within the
  platform limit before an official upload or review window; TTL is not a data
  backup strategy.
