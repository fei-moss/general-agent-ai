# Marketplace QnA RAG Ingestion Runbook

## Purpose

This runbook is the repeatable operator flow for `SPEC-RAG-EVAL-002`. It covers
the 9 Chinese and 9 English Marketplace QnA Markdown files, persistent pgvector
ingestion, local semantic evaluation, live DockerHost retrieval, and live chat
acceptance through the server-owned default knowledge base.

The RAG administrator is an internal runtime identity. Store it in macOS
Keychain or an approved secret manager only; never place it in Git, command
output, release artifacts, or chat metadata.

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

Verify the deterministic fixture family first:

```bash
.venv/bin/python tests/rag_eval/marketplace_qna_fixture_builder.py
.venv/bin/python -m tests.rag_eval.marketplace_qna_golden_query_audit \
  --output .artifacts/release/marketplace_qna_golden_query_audit.json
.venv/bin/python -m tests.rag_eval.moss_gemini_preflight \
  --output .artifacts/release/marketplace_qna_gemini_preflight.json \
  --model gemini-embedding-2 --dimension 256
.venv/bin/python -m pytest -q tests/test_marketplace_qna_eval.py \
  tests/test_rag_promptfoo_eval.py
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

Run the production embedding model and production chunk settings:

```bash
PROMPTFOO_PYTHON=.venv/bin/python npx --yes promptfoo@latest eval \
  -c tests/rag_eval/marketplace_qna_promptfooconfig.yaml \
  --no-cache \
  --output .artifacts/release/marketplace_qna_promptfoo_eval.json
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
.venv/bin/python -m tests.rag_eval.marketplace_qna_live_eval \
  --base-url <api_base_url> \
  --knowledge-base-id <knowledge_base_id> \
  --retrieval-workers 4 \
  --chat-timeout-s 120
```

The chat payload intentionally contains no `knowledge_base_id`. Every one of
the 18 chat cases must reach `SUCCEEDED`, emit `RETRIEVAL_STARTED` and
`RETRIEVAL_FINISHED`, include all required fact groups, and contain no forbidden
claim.

After `scripts/verify_release.sh` passes, produce the final status:

```bash
.venv/bin/python -m tests.rag_eval.marketplace_qna_acceptance_validator
.venv/bin/python -m tests.rag_eval.marketplace_qna_acceptance_status \
  --output .artifacts/release/marketplace_qna_acceptance_status.json
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
