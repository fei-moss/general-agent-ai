# MOSS RAG Ingestion Runbook

## Purpose

This runbook describes how to ingest the expanded reviewed MOSS Wiki seed into the persistent RAG system.

Source manifest: `moss-wiki-rag-seed-v2` in `tests/rag_eval/moss_rag_seed_manifest.json`.

Acceptance evidence contract:

- `SPEC-RAG-EVAL-001-MOSS-ACCEPTANCE-EVIDENCE`

## Preconditions

- Persistent DockerHost environment exists: `chris-general-agent-ai-rag`.
- API, worker, Postgres, Redis, and pgvector are running.
- `CREATE EXTENSION IF NOT EXISTS vector;` has been applied.
- Runtime embedding config matches the seed manifest:
  - `EMBEDDING_PROVIDER=gemini`
  - `EMBEDDING_MODEL=gemini-embedding-2`
  - `EMBEDDING_DIM=256`
- Gemini API key is injected through local/secret-manager environment; never commit or print it.
- The caller IP is allowed by Gemini for the configured key.

## Seed Files

| Role | Path | Rows |
| --- | --- | ---: |
| `corpus` | `tests/rag_eval/moss_corpus.jsonl` | 40 |
| `golden_queries` | `tests/rag_eval/moss_golden_queries.jsonl` | 79 |
| `review_evidence` | `tests/rag_eval/moss_golden_query_review.jsonl` | 79 |
| `coverage_contract` | `tests/rag_eval/moss_coverage_contract.json` | n/a |

## Preflight

Verify reviewed fixture hashes:

```bash
shasum -a 256 \
  tests/rag_eval/moss_corpus.jsonl \
  tests/rag_eval/moss_golden_queries.jsonl \
  tests/rag_eval/moss_golden_query_review.jsonl \
  tests/rag_eval/moss_coverage_contract.json
```

The SHA-256 output must match the `checksums.sha256` entries in
`tests/rag_eval/moss_rag_seed_manifest.json`.

Run local contract checks:

```bash
.venv/bin/python -m pytest tests/test_rag_promptfoo_eval.py -q
make verify-release
```

Write the Golden Query audit report:

```bash
.venv/bin/python -m tests.rag_eval.moss_golden_query_audit \
  --output .artifacts/release/moss_golden_query_audit.json
```

Verify Gemini embedding access:

```bash
source /Users/chris/.codex-local/general-agent-ai/gemini_env.sh
.venv/bin/python -m tests.rag_eval.moss_gemini_preflight \
  --output .artifacts/release/moss_gemini_preflight.json
```

The underlying API shape uses `embedContent`:

```bash
curl -sS -w '
HTTP_STATUS:%{http_code}
' \
  'https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent' \
  -H 'Content-Type: application/json' \
  -H "x-goog-api-key: ${GEMINI_API_KEY}" \
  -d '{"model":"models/gemini-embedding-2","content":{"parts":[{"text":"MOSS RAG eval smoke"}]},"outputDimensionality":256}'
```

If the result contains `API_KEY_IP_ADDRESS_BLOCKED`, fix the Gemini key/IP restriction and rerun preflight. Do not substitute hash embeddings for acceptance.

Generate deterministic `/rag/documents` payloads:

```bash
.venv/bin/python -m tests.rag_eval.moss_import_payloads \
  --knowledge-base-id <knowledge_base_id> \
  > .artifacts/release/moss_rag_document_payloads.jsonl
```

## API Import Flow

1. Create the target knowledge base.

```http
POST /rag/knowledge-bases
X-User-Id: <operator-user-id>
Content-Type: application/json

{
  "name": "MOSS Wiki",
  "description": "Expanded reviewed source-backed MOSS Wiki corpus."
}
```

2. Submit one document per row in `tests/rag_eval/moss_corpus.jsonl` through `POST /rag/documents`.

3. Poll each returned ingestion job until `SUCCEEDED`.

```http
GET /rag/ingestion-jobs/{job_id}
X-User-Id: <operator-user-id>
```

4. Run a smoke query.

```http
POST /rag/query
X-User-Id: <operator-user-id>
Content-Type: application/json

{
  "knowledge_base_id": "<knowledge_base_id>",
  "query": "MOSS Agent 会动用真实资金吗？",
  "top_k": 5,
  "strict": true
}
```

5. Persist the ingestion summary evidence.

Write `.artifacts/release/moss_rag_ingestion_summary.json` with the DockerHost
environment name, knowledge base id, submitted document count, persisted
document count, succeeded/failed ingestion job counts, persisted chunk count,
distinct source document count, embedding provider/model counts, and smoke-query
top chunks.

6. Run semantic eval.

```bash
PROMPTFOO_PYTHON=.venv/bin/python npx --yes promptfoo@latest eval \
  -c tests/rag_eval/moss_promptfooconfig.yaml \
  --no-cache \
  --output .artifacts/release/moss_rag_promptfoo_eval.json
```

7. Generate acceptance status for release artifacts.

```bash
.venv/bin/python -m tests.rag_eval.moss_acceptance_status \
  --output .artifacts/release/moss_rag_acceptance_status.json
```

## Acceptance Criteria

- 40 MOSS corpus rows are submitted.
- 40 ingestion jobs finish as `SUCCEEDED`.
- `/rag/query` returns non-degraded source-backed results.
- Persistent import writes `.artifacts/release/moss_rag_ingestion_summary.json`.
- MOSS semantic Promptfoo eval writes `.artifacts/release/moss_rag_promptfoo_eval.json`.
- Acceptance status writes `.artifacts/release/moss_rag_acceptance_status.json`.
- `.venv/bin/python -m tests.rag_eval.moss_acceptance_validator` passes.
