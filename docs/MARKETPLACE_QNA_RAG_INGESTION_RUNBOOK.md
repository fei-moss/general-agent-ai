# Marketplace QnA RAG Ingestion Runbook

## Purpose

This runbook is the repeatable operator flow for `SPEC-RAG-EVAL-002`. It covers
the 9 Chinese and 9 English Marketplace QnA Markdown files, persistent pgvector
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
- Embeddings use Gemini `gemini-embedding-2` with dimension `256`.
- The internal administrator is included in `RAG_ADMIN_USER_IDS`.
- `RAG_DEFAULT_KNOWLEDGE_BASE_ID` and `RAG_INTERNAL_OWNER_USER_ID` are set on
  the server; `RAG_ALLOW_CLIENT_KNOWLEDGE_BASE_ID=false`.
- Runtime provider keys are injected with `--secret-env` or `--secret-file`,
  never inline.

## Reviewed Seed

| Role | Path | Rows |
| --- | --- | ---: |
| Corpus | `tests/rag_eval/marketplace_qna_corpus.jsonl` | 18 |
| Golden queries | `tests/rag_eval/marketplace_qna_golden_queries.jsonl` | 114 |
| Review evidence | `tests/rag_eval/marketplace_qna_golden_query_review.jsonl` | 114 |
| Chat cases | `tests/rag_eval/marketplace_qna_chat_cases.jsonl` | 18 |

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
3. Generate the 18 schema-valid request bodies:

```bash
.venv/bin/python -m tests.rag_eval.marketplace_qna_import_payloads \
  --knowledge-base-id <knowledge_base_id>
```

4. Submit every body through `POST /rag/documents` as the RAG administrator.
5. Poll `GET /rag/ingestion-jobs/{job_id}` until every job is terminal.
6. Require 18 `SUCCEEDED`, 0 failed, 18 persisted documents, 141 chunks, and
   equality between uploaded SHA-256 metadata and the source manifest.
7. Save the redacted result as
   `.artifacts/release/marketplace_qna_ingestion_summary.json`.

Repeating the same payload is an idempotency check. It must not create a second
logical document or duplicate chunks.

## Local Semantic Evaluation

Run Gemini preflight and the 114-case Promptfoo suite with production embedding
and chunk settings:

```bash
make marketplace-qna-local
```

Acceptance requires 114/114 top-5 passes, no degraded cases, and Top-1 at least
80%. Retrieval is filtered to the query language so mirrored Chinese and
English documents do not compete with each other.

## Server Default Knowledge Base

Deploy through the existing branch space after pushing the Git ref. Re-pass all
one-shot secrets on every deployment:

```bash
source /Users/chris/.codex-local/dockerhost/envctl_env.sh
envctl branch-space deploy --name <environment> \
  --secret-env RAG_ADMIN_USER_IDS \
  --secret-env RAG_INTERNAL_OWNER_USER_ID \
  --secret-env RAG_DEFAULT_KNOWLEDGE_BASE_ID
envctl branch-space status --name <environment>
```

Use the repository release wrapper instead when it is the current documented
deployment authority. Do not run `down`, recreate the environment, or remove
the managed PostgreSQL volume for a normal corpus refresh.

## Live Acceptance

The evaluator reads the admin ID from Keychain by default and generates one
ephemeral Marketplace test identity when chat identity variables are absent.
Raw identities are redacted before evidence is written.

```bash
make marketplace-qna-live
```

The chat payload intentionally contains no `knowledge_base_id`. Every one of
the 18 chat cases must reach `SUCCEEDED`, emit `RETRIEVAL_STARTED` and
`RETRIEVAL_FINISHED`, include all required fact groups, and contain no forbidden
claim.

Run the repository release harness and produce the final acceptance status:

```bash
make marketplace-qna-final
```

## Rollback and Retention

- To stop chat from using this corpus, redeploy with
  `RAG_DEFAULT_KNOWLEDGE_BASE_ID` and `RAG_INTERNAL_OWNER_USER_ID` unset while
  retaining the PostgreSQL volume.
- Keep the knowledge base and evidence until the replacement corpus has passed
  the same contract.
- Branch spaces have platform TTLs. Check and extend the environment within the
  platform limit before an official upload or review window; TTL is not a data
  backup strategy.
