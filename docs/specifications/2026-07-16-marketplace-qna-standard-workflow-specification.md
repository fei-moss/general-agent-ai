# Marketplace QnA Standard Acceptance Workflow Specification

- Spec ID: `SPEC-RAG-EVAL-003`
- Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`
- Extends: `SPEC-RAG-EVAL-002`

## Problem Assessment

The first Marketplace QnA release reached its quality target, but the path was
longer than necessary because acceptance prerequisites were discovered in
sequence. The durable causes were:

- provider batching, bilingual ranking, and live SSE behavior were not checked
  with a small preflight before the full suite;
- local, ingestion, live, and release commands had separate entry points;
- the final validator was authoritative, but operators could still omit an
  earlier command and discover the missing artifact late;
- exact answer phrases initially confused evaluator noise with product or
  corpus defects.

The source upload and RAG runtime were not the root problem. The missing piece
was a small mechanical orchestration layer over the already-correct tools.

## Goal

Provide one concise, fail-fast operator workflow that runs the existing
Marketplace QnA authorities in the required order without duplicating their
logic.

## Design

The workflow has exactly five gates:

1. **Preflight** — validate required environment variables, the ingestion
   summary prerequisite, fixture hashes, coverage, and focused contracts.
2. **Local** — run Gemini 256-dimensional preflight and the 114-case Promptfoo
   semantic suite.
3. **Ingestion** — treat the existing redacted ingestion summary as the
   boundary proof; uploading remains an explicit operator action because it
   mutates persistent data.
4. **Live** — run 114 strict retrieval cases and 18 server-default-KB chat
   cases against the supplied API base URL and knowledge-base id.
5. **Final** — run the repository release harness, acceptance validator, and
   acceptance status writer.

The Makefile exposes one target per gate plus one aggregate target. It only
composes existing Python modules and Promptfoo. It must not add a second
validator, retry semantic failures, upload documents automatically, deploy an
environment, or read provider secrets from repository files.

## Operator Contract

Required exported values for a full run:

- `GEMINI_API_KEY`
- `MARKETPLACE_QNA_BASE_URL`
- `MARKETPLACE_QNA_KNOWLEDGE_BASE_ID`

The RAG administrator continues to come from the existing Keychain lookup or
`RAG_ADMIN_USER_ID`. The workflow fails before provider calls when a required
value or ingestion summary is missing.

Canonical commands:

```bash
make marketplace-qna-preflight
make marketplace-qna-local
make marketplace-qna-live
make marketplace-qna-final
make marketplace-qna-acceptance
```

`marketplace-qna-acceptance` runs preflight, local, live, and final in that
order. The ingestion gate is represented by preflight validation of
`.artifacts/release/marketplace_qna_ingestion_summary.json`; the persistent
upload itself remains governed by the ingestion runbook.

## Acceptance Criteria

- Makefile help names all five operator targets and their scope.
- A contract test proves the aggregate target orders preflight before local,
  local before live, and live before final.
- Preflight fails before network/provider work when required variables or the
  ingestion summary are missing.
- The local target writes the contracted Gemini and Promptfoo artifacts.
- The live target writes the contracted retrieval and chat artifacts.
- The final target runs `scripts/verify_release.sh`, the acceptance validator,
  and the acceptance status writer.
- No runtime, API, task, database, authentication, or deployment behavior is
  changed.
- Focused tests, `git diff --check`, and `scripts/verify_release.sh` pass.

## Failure Classification

- Missing variables, artifacts, hashes, or counts are workflow failures.
- HTTP, SSE, provider, or timeout errors remain transport failures in live
  evidence.
- Missing expected facts or source matches are semantic failures and are not
  retried into a pass.
- Source-specific ambiguity is recorded as a corpus defect; evaluator synonym
  gaps are fixed with source-backed regression tests.

## Non-Goals

- No generic workflow engine.
- No automatic DockerHost deployment or persistent upload.
- No new LLM judge.
- No CI execution of provider-backed or live gates.
- No second copy of acceptance thresholds outside the existing evidence
  contract.
