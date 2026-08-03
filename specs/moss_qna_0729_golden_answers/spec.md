---
spec_id: SPEC-MOSS-QNA-0729-GOLDEN-ANSWERS-001
module: moss_qna_0729_golden_answers
status: implemented
workflow_class: HARNESS-SPEC-FIRST-FEATURE
---

# Moss QnA 0729 Golden Answers

## Specification

### Source And Scope

- Product-owner-approved source: `/root/Documents/moss-qna-cn-0729.md` and
  `/root/Documents/moss-qna-en-0729.md` (34 bilingual QnA pairs, ops golden
  cases dated 2026-07-29; owner approved corpus promotion on 2026-08-03 by
  choosing direct merge without a prior live baseline).
- Trading-Agent content (22 pairs) is applicable to Agent type `hyperliquid`;
  governance content (12 pairs) is applicable to Agent type `ballot`.
- The batch is incremental Golden Case evidence; it does not enumerate every
  Marketplace behavior.

### Behavior

- `SPEC-MOSS-QNA-0729-GOLDEN-ANSWERS-001-R1`: the stable mechanics from the
  approved source are merged into the canonical Marketplace QnA corpus as two
  new bilingual source documents per language
  (`11_交易-Agent-角色与资金安全` / `11_Trading-Agent-Roles-and-Fund-Safety`,
  `12_治理投票与收益细节` / `12_Governance-Voting-and-Yield-Details`), producing
  source set `marketplace-qna-bilingual-2026-08-03-v6` and manifest
  `marketplace-qna-rag-seed-v6`.
- `SPEC-MOSS-QNA-0729-GOLDEN-ANSWERS-001-R2`: per-Agent dynamic values stay out
  of the fixed corpus. The source claims "management fee is currently 0%" and
  "settlement currently runs once a day" are current-Agent configuration; the
  v6 documents state that fee schedule and settlement timing come from current
  Agent context, and only the stable facts (gas goes to the network, settlement
  produces the share price) are fixed knowledge.
- `SPEC-MOSS-QNA-0729-GOLDEN-ANSWERS-001-R3`: the approved source hardens three
  previously dynamic governance statements into platform mechanics: the voting
  snapshot is taken at proposal creation, voting is an on-chain action that
  costs gas, and rewards are claimed together with redemption. Document 10 was
  aligned in both languages so the corpus carries a single reading.
- `SPEC-MOSS-QNA-0729-GOLDEN-ANSWERS-001-R4`: two source asymmetries between
  the Chinese and English 0729 files were normalized: the settlement-cadence
  sentence present only in English was replaced by the dynamic-configuration
  phrasing in both languages, and the Owner private-key answers were unified
  (user-held key, signed directly in the user's own wallet).
- `SPEC-MOSS-QNA-0729-GOLDEN-ANSWERS-001-R5`: every new source question has one
  same-language semantic retrieval Golden Query with verbatim answer evidence;
  totals become 24 documents, 218 Golden Queries, 218 review rows, 24
  representative chat cases, and 241 ingestion chunks under the production
  chunker settings.

## Implementation Plan

1. Author the four new bilingual source documents and align document 10
   (snapshot timing, vote gas) in both languages.
2. Extend `marketplace_qna_case_definitions.jsonl` with 68 reviewed rows
   (paraphrased query, verbatim answer claim, four representative chat cases)
   and refresh the two document-10 rows whose quoted answers changed.
3. Update `marketplace_qna_fixture_builder.py` (corpus version, expected
   question counts, chat fact groups) and the audit/test constants
   (24/218/24/241) through the code-change workflow.
4. Regenerate the four fixture files with the builder, then update the coverage
   contract, acceptance evidence contract, and seed manifest (ids, counts,
   hashes) and the runbook/review documents.
5. Validate with the fixture audit, the marketplace QnA test suites, and the
   full local test run. Persistent upload, DockerHost deployment, and
   `RAG_DEFAULT_KNOWLEDGE_BASE_ID` switching remain explicit operator steps per
   the ingestion runbook, with the V5 knowledge base retained for rollback.

## Closeout Evidence

- Normalized approved-case batch (68 cases, `ops-moss-qna-0729`) ingested and
  frozen via `tests.chat_eval.approved_case_workflow` on 2026-08-03; preflight
  is `blocked` pending target-truth and live identity, and the owner elected to
  skip the live baseline for this batch.
- `python -m tests.rag_eval.marketplace_qna_fixture_builder --write` reports
  24 sources, 218 golden queries, 218 review rows, 24 chat cases.
- `python -m tests.rag_eval.marketplace_qna_golden_query_audit` passed against
  the v6 fixtures and contracts.
- Full local pytest suite passed on 2026-08-03 (proxy variables unset for the
  provider-client construction tests; the SOCKS-proxy import failure is a host
  environment issue unrelated to this change).
- The local Gemini semantic evaluation (`make marketplace-qna-local`) could not
  run from this host: the embedding key rejects both available proxy exits with
  `API_KEY_IP_ADDRESS_BLOCKED`. It remains part of the operator acceptance
  before upload.
- Live corpus promotion completed on 2026-08-03 against
  `chris-general-agent-ai-chat-prod` (release commit `b64ba54`, previous
  release `f5523e5` retained as rollback ref):
  - `VERIFY_COMPARE_REF=f5523e5 make verify-release` all gates PASS before push.
  - Knowledge base `kb_0b163eb7369b4589aa3fcb0d5b78e3f0` ("Moss Agent
    Marketplace QnA V6") created through `POST /rag/knowledge-bases`; 24
    documents imported, 24 ingestion jobs `SUCCEEDED`, 0 failed, 241 chunks
    (worker-log task results; per-document counts match the local chunker),
    SHA-256 metadata equal to `marketplace-qna-rag-seed-v6`; resubmitting all
    24 payloads returned `replayed=true` for every document (idempotency).
    Redacted summary: `.artifacts/release/marketplace_qna_ingestion_summary.json`.
  - `scripts/dockerhost_release.py redeploy --execute` with
    `RAG_DEFAULT_KNOWLEDGE_BASE_ID` switched to the V6 knowledge base: all 17
    audited steps passed (preflight, branch-space switch/deploy, healthz,
    readyz, stream=false 422, accepted chat, SSE, run status, worker/reaper
    logs). The V5 knowledge base is retained for rollback.
  - Post-deploy verification on the server-default knowledge base: three
    `/rag/query` spot checks hit the new documents at rank 1 in both
    languages, and two live `/chat` runs answered from the new corpus
    (Trading Wallet 90-day authorization in Chinese; snapshot-at-proposal-
    creation voting rule in English).
- Remaining operator acceptance: the full `make marketplace-qna-acceptance`
  suite (Gemini preflight, 218-case Promptfoo semantic evaluation, 218-case
  live retrieval, 24-case live chat) has not run because the embedding key
  rejects this host's egress IPs; run it from an allowlisted environment per
  `docs/MARKETPLACE_QNA_RAG_INGESTION_RUNBOOK.md`.
