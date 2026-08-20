# Marketplace QnA Golden Queries Review

## Scope

This review is the human-readable evidence for `SPEC-RAG-EVAL-002`. The current V7 seed (`marketplace-qna-rag-seed-v7`) contains 16 Chinese and 16 English Marketplace QnA Markdown files. It covers 316 source questions with one same-language semantic retrieval case per question and 32 representative end-to-end chat cases. V7 retains the V6 trading and governance material and adds owner-approved stable Consumer/Redemption and PixVerse mechanisms. Current-Agent thresholds, amounts, fees, code details, entry points, support routes, identity values, addresses, and networks remain outside the fixed corpus.

Machine-readable authorities:

- `tests/rag_eval/marketplace_qna_rag_seed_manifest.json`
- `tests/rag_eval/marketplace_qna_coverage_contract.json`
- `tests/rag_eval/marketplace_qna_acceptance_evidence_contract.json`
- `tests/rag_eval/marketplace_qna_golden_query_review.jsonl`
- `tests/rag_eval/marketplace_qna_chat_cases.jsonl`

## Review Conclusion

The fixture family has complete source-question coverage: 32 documents, 316 Golden Queries, 316 review rows, and 32 chat cases. Chinese and English each contribute 158 retrieval cases. Every case points to exactly one expected source document and a source answer line range.

The current acceptance target is deliberately strict:

- local Promptfoo: 316/316 top-5, zero degraded, Top-1 at least 80%;
- DockerHost `/rag/query`: 316/316 top-5 with the same language filter, zero degraded, Top-1 at least 80%;
- live chat: 32/32 terminal `SUCCEEDED`, server-default knowledge base, RAG start/finish evidence, all required fact groups, no forbidden claims;
- persistent ingestion: 32 documents, 32 successful jobs, 289 chunks, zero failed jobs, exact source-hash equality.

## Corpus Quality Finding

### CORPUS-MPQNA-001 — Resolved in V2: Tool-built versus template-deployed Agent

Source: `tests/rag_eval/marketplace_qna_sources/zh-CN/08_安全与风险.md:43-45`.

V2 now states the layer distinction, explicitly rejects official endorsement or risk guarantees, and names the evidence users should assess: on-chain records, creator disclosures, contract parameters, trading history, and risk controls. It also cross-references the Discover guidance. The earlier corpus-specificity finding is therefore closed; the V2 required fact is checked directly against this answer block.

## Golden Query Inventory

| Expected document | Cases | Golden Query ids |
| --- | ---: | --- |
| `marketplace_qna_en_01` | 5 | `marketplace_qna_en_01_q01`, `marketplace_qna_en_01_q02`, `marketplace_qna_en_01_q03`, `marketplace_qna_en_01_q04`, `marketplace_qna_en_01_q05` |
| `marketplace_qna_en_02` | 7 | `marketplace_qna_en_02_q01`, `marketplace_qna_en_02_q02`, `marketplace_qna_en_02_q03`, `marketplace_qna_en_02_q04`, `marketplace_qna_en_02_q05`, `marketplace_qna_en_02_q06`, `marketplace_qna_en_02_q07` |
| `marketplace_qna_en_03` | 2 | `marketplace_qna_en_03_q01`, `marketplace_qna_en_03_q02` |
| `marketplace_qna_en_04` | 16 | `marketplace_qna_en_04_q01`, `marketplace_qna_en_04_q02`, `marketplace_qna_en_04_q03`, `marketplace_qna_en_04_q04`, `marketplace_qna_en_04_q05`, `marketplace_qna_en_04_q06`, `marketplace_qna_en_04_q07`, `marketplace_qna_en_04_q08`, `marketplace_qna_en_04_q09`, `marketplace_qna_en_04_q10`, `marketplace_qna_en_04_q11`, `marketplace_qna_en_04_q12`, `marketplace_qna_en_04_q13`, `marketplace_qna_en_04_q14`, `marketplace_qna_en_04_q15`, `marketplace_qna_en_04_q16` |
| `marketplace_qna_en_05` | 4 | `marketplace_qna_en_05_q01`, `marketplace_qna_en_05_q02`, `marketplace_qna_en_05_q03`, `marketplace_qna_en_05_q04` |
| `marketplace_qna_en_06` | 9 | `marketplace_qna_en_06_q01`, `marketplace_qna_en_06_q02`, `marketplace_qna_en_06_q03`, `marketplace_qna_en_06_q04`, `marketplace_qna_en_06_q05`, `marketplace_qna_en_06_q06`, `marketplace_qna_en_06_q07`, `marketplace_qna_en_06_q08`, `marketplace_qna_en_06_q09` |
| `marketplace_qna_en_07` | 4 | `marketplace_qna_en_07_q01`, `marketplace_qna_en_07_q02`, `marketplace_qna_en_07_q03`, `marketplace_qna_en_07_q04` |
| `marketplace_qna_en_08` | 7 | `marketplace_qna_en_08_q01`, `marketplace_qna_en_08_q02`, `marketplace_qna_en_08_q03`, `marketplace_qna_en_08_q04`, `marketplace_qna_en_08_q05`, `marketplace_qna_en_08_q06`, `marketplace_qna_en_08_q07` |
| `marketplace_qna_en_09` | 3 | `marketplace_qna_en_09_q01`, `marketplace_qna_en_09_q02`, `marketplace_qna_en_09_q03` |
| `marketplace_qna_en_10` | 18 | `marketplace_qna_en_10_q01`, `marketplace_qna_en_10_q02`, `marketplace_qna_en_10_q03`, `marketplace_qna_en_10_q04`, `marketplace_qna_en_10_q05`, `marketplace_qna_en_10_q06`, `marketplace_qna_en_10_q07`, `marketplace_qna_en_10_q08`, `marketplace_qna_en_10_q09`, `marketplace_qna_en_10_q10`, `marketplace_qna_en_10_q11`, `marketplace_qna_en_10_q12`, `marketplace_qna_en_10_q13`, `marketplace_qna_en_10_q14`, `marketplace_qna_en_10_q15`, `marketplace_qna_en_10_q16`, `marketplace_qna_en_10_q17`, `marketplace_qna_en_10_q18` |
| `marketplace_qna_en_11` | 22 | `marketplace_qna_en_11_q01`, `marketplace_qna_en_11_q02`, `marketplace_qna_en_11_q03`, `marketplace_qna_en_11_q04`, `marketplace_qna_en_11_q05`, `marketplace_qna_en_11_q06`, `marketplace_qna_en_11_q07`, `marketplace_qna_en_11_q08`, `marketplace_qna_en_11_q09`, `marketplace_qna_en_11_q10`, `marketplace_qna_en_11_q11`, `marketplace_qna_en_11_q12`, `marketplace_qna_en_11_q13`, `marketplace_qna_en_11_q14`, `marketplace_qna_en_11_q15`, `marketplace_qna_en_11_q16`, `marketplace_qna_en_11_q17`, `marketplace_qna_en_11_q18`, `marketplace_qna_en_11_q19`, `marketplace_qna_en_11_q20`, `marketplace_qna_en_11_q21`, `marketplace_qna_en_11_q22` |
| `marketplace_qna_en_12` | 12 | `marketplace_qna_en_12_q01`, `marketplace_qna_en_12_q02`, `marketplace_qna_en_12_q03`, `marketplace_qna_en_12_q04`, `marketplace_qna_en_12_q05`, `marketplace_qna_en_12_q06`, `marketplace_qna_en_12_q07`, `marketplace_qna_en_12_q08`, `marketplace_qna_en_12_q09`, `marketplace_qna_en_12_q10`, `marketplace_qna_en_12_q11`, `marketplace_qna_en_12_q12` |
| `marketplace_qna_zh_cn_01` | 5 | `marketplace_qna_zh_cn_01_q01`, `marketplace_qna_zh_cn_01_q02`, `marketplace_qna_zh_cn_01_q03`, `marketplace_qna_zh_cn_01_q04`, `marketplace_qna_zh_cn_01_q05` |
| `marketplace_qna_zh_cn_02` | 7 | `marketplace_qna_zh_cn_02_q01`, `marketplace_qna_zh_cn_02_q02`, `marketplace_qna_zh_cn_02_q03`, `marketplace_qna_zh_cn_02_q04`, `marketplace_qna_zh_cn_02_q05`, `marketplace_qna_zh_cn_02_q06`, `marketplace_qna_zh_cn_02_q07` |
| `marketplace_qna_zh_cn_03` | 2 | `marketplace_qna_zh_cn_03_q01`, `marketplace_qna_zh_cn_03_q02` |
| `marketplace_qna_zh_cn_04` | 16 | `marketplace_qna_zh_cn_04_q01`, `marketplace_qna_zh_cn_04_q02`, `marketplace_qna_zh_cn_04_q03`, `marketplace_qna_zh_cn_04_q04`, `marketplace_qna_zh_cn_04_q05`, `marketplace_qna_zh_cn_04_q06`, `marketplace_qna_zh_cn_04_q07`, `marketplace_qna_zh_cn_04_q08`, `marketplace_qna_zh_cn_04_q09`, `marketplace_qna_zh_cn_04_q10`, `marketplace_qna_zh_cn_04_q11`, `marketplace_qna_zh_cn_04_q12`, `marketplace_qna_zh_cn_04_q13`, `marketplace_qna_zh_cn_04_q14`, `marketplace_qna_zh_cn_04_q15`, `marketplace_qna_zh_cn_04_q16` |
| `marketplace_qna_zh_cn_05` | 4 | `marketplace_qna_zh_cn_05_q01`, `marketplace_qna_zh_cn_05_q02`, `marketplace_qna_zh_cn_05_q03`, `marketplace_qna_zh_cn_05_q04` |
| `marketplace_qna_zh_cn_06` | 9 | `marketplace_qna_zh_cn_06_q01`, `marketplace_qna_zh_cn_06_q02`, `marketplace_qna_zh_cn_06_q03`, `marketplace_qna_zh_cn_06_q04`, `marketplace_qna_zh_cn_06_q05`, `marketplace_qna_zh_cn_06_q06`, `marketplace_qna_zh_cn_06_q07`, `marketplace_qna_zh_cn_06_q08`, `marketplace_qna_zh_cn_06_q09` |
| `marketplace_qna_zh_cn_07` | 4 | `marketplace_qna_zh_cn_07_q01`, `marketplace_qna_zh_cn_07_q02`, `marketplace_qna_zh_cn_07_q03`, `marketplace_qna_zh_cn_07_q04` |
| `marketplace_qna_zh_cn_08` | 7 | `marketplace_qna_zh_cn_08_q01`, `marketplace_qna_zh_cn_08_q02`, `marketplace_qna_zh_cn_08_q03`, `marketplace_qna_zh_cn_08_q04`, `marketplace_qna_zh_cn_08_q05`, `marketplace_qna_zh_cn_08_q06`, `marketplace_qna_zh_cn_08_q07` |
| `marketplace_qna_zh_cn_09` | 3 | `marketplace_qna_zh_cn_09_q01`, `marketplace_qna_zh_cn_09_q02`, `marketplace_qna_zh_cn_09_q03` |
| `marketplace_qna_zh_cn_10` | 18 | `marketplace_qna_zh_cn_10_q01`, `marketplace_qna_zh_cn_10_q02`, `marketplace_qna_zh_cn_10_q03`, `marketplace_qna_zh_cn_10_q04`, `marketplace_qna_zh_cn_10_q05`, `marketplace_qna_zh_cn_10_q06`, `marketplace_qna_zh_cn_10_q07`, `marketplace_qna_zh_cn_10_q08`, `marketplace_qna_zh_cn_10_q09`, `marketplace_qna_zh_cn_10_q10`, `marketplace_qna_zh_cn_10_q11`, `marketplace_qna_zh_cn_10_q12`, `marketplace_qna_zh_cn_10_q13`, `marketplace_qna_zh_cn_10_q14`, `marketplace_qna_zh_cn_10_q15`, `marketplace_qna_zh_cn_10_q16`, `marketplace_qna_zh_cn_10_q17`, `marketplace_qna_zh_cn_10_q18` |
| `marketplace_qna_zh_cn_11` | 22 | `marketplace_qna_zh_cn_11_q01`, `marketplace_qna_zh_cn_11_q02`, `marketplace_qna_zh_cn_11_q03`, `marketplace_qna_zh_cn_11_q04`, `marketplace_qna_zh_cn_11_q05`, `marketplace_qna_zh_cn_11_q06`, `marketplace_qna_zh_cn_11_q07`, `marketplace_qna_zh_cn_11_q08`, `marketplace_qna_zh_cn_11_q09`, `marketplace_qna_zh_cn_11_q10`, `marketplace_qna_zh_cn_11_q11`, `marketplace_qna_zh_cn_11_q12`, `marketplace_qna_zh_cn_11_q13`, `marketplace_qna_zh_cn_11_q14`, `marketplace_qna_zh_cn_11_q15`, `marketplace_qna_zh_cn_11_q16`, `marketplace_qna_zh_cn_11_q17`, `marketplace_qna_zh_cn_11_q18`, `marketplace_qna_zh_cn_11_q19`, `marketplace_qna_zh_cn_11_q20`, `marketplace_qna_zh_cn_11_q21`, `marketplace_qna_zh_cn_11_q22` |
| `marketplace_qna_zh_cn_12` | 12 | `marketplace_qna_zh_cn_12_q01`, `marketplace_qna_zh_cn_12_q02`, `marketplace_qna_zh_cn_12_q03`, `marketplace_qna_zh_cn_12_q04`, `marketplace_qna_zh_cn_12_q05`, `marketplace_qna_zh_cn_12_q06`, `marketplace_qna_zh_cn_12_q07`, `marketplace_qna_zh_cn_12_q08`, `marketplace_qna_zh_cn_12_q09`, `marketplace_qna_zh_cn_12_q10`, `marketplace_qna_zh_cn_12_q11`, `marketplace_qna_zh_cn_12_q12` |
| `marketplace_qna_en_13` | 12 | `marketplace_qna_en_13_q01`, `marketplace_qna_en_13_q02`, `marketplace_qna_en_13_q03`, `marketplace_qna_en_13_q04`, `marketplace_qna_en_13_q05`, `marketplace_qna_en_13_q06`, `marketplace_qna_en_13_q07`, `marketplace_qna_en_13_q08`, `marketplace_qna_en_13_q09`, `marketplace_qna_en_13_q10`, `marketplace_qna_en_13_q11`, `marketplace_qna_en_13_q12` |
| `marketplace_qna_en_14` | 8 | `marketplace_qna_en_14_q01`, `marketplace_qna_en_14_q02`, `marketplace_qna_en_14_q03`, `marketplace_qna_en_14_q04`, `marketplace_qna_en_14_q05`, `marketplace_qna_en_14_q06`, `marketplace_qna_en_14_q07`, `marketplace_qna_en_14_q08` |
| `marketplace_qna_en_15` | 18 | `marketplace_qna_en_15_q01`, `marketplace_qna_en_15_q02`, `marketplace_qna_en_15_q03`, `marketplace_qna_en_15_q04`, `marketplace_qna_en_15_q05`, `marketplace_qna_en_15_q06`, `marketplace_qna_en_15_q07`, `marketplace_qna_en_15_q08`, `marketplace_qna_en_15_q09`, `marketplace_qna_en_15_q10`, `marketplace_qna_en_15_q11`, `marketplace_qna_en_15_q12`, `marketplace_qna_en_15_q13`, `marketplace_qna_en_15_q14`, `marketplace_qna_en_15_q15`, `marketplace_qna_en_15_q16`, `marketplace_qna_en_15_q17`, `marketplace_qna_en_15_q18` |
| `marketplace_qna_en_16` | 11 | `marketplace_qna_en_16_q01`, `marketplace_qna_en_16_q02`, `marketplace_qna_en_16_q03`, `marketplace_qna_en_16_q04`, `marketplace_qna_en_16_q05`, `marketplace_qna_en_16_q06`, `marketplace_qna_en_16_q07`, `marketplace_qna_en_16_q08`, `marketplace_qna_en_16_q09`, `marketplace_qna_en_16_q10`, `marketplace_qna_en_16_q11` |
| `marketplace_qna_zh_cn_13` | 12 | `marketplace_qna_zh_cn_13_q01`, `marketplace_qna_zh_cn_13_q02`, `marketplace_qna_zh_cn_13_q03`, `marketplace_qna_zh_cn_13_q04`, `marketplace_qna_zh_cn_13_q05`, `marketplace_qna_zh_cn_13_q06`, `marketplace_qna_zh_cn_13_q07`, `marketplace_qna_zh_cn_13_q08`, `marketplace_qna_zh_cn_13_q09`, `marketplace_qna_zh_cn_13_q10`, `marketplace_qna_zh_cn_13_q11`, `marketplace_qna_zh_cn_13_q12` |
| `marketplace_qna_zh_cn_14` | 8 | `marketplace_qna_zh_cn_14_q01`, `marketplace_qna_zh_cn_14_q02`, `marketplace_qna_zh_cn_14_q03`, `marketplace_qna_zh_cn_14_q04`, `marketplace_qna_zh_cn_14_q05`, `marketplace_qna_zh_cn_14_q06`, `marketplace_qna_zh_cn_14_q07`, `marketplace_qna_zh_cn_14_q08` |
| `marketplace_qna_zh_cn_15` | 18 | `marketplace_qna_zh_cn_15_q01`, `marketplace_qna_zh_cn_15_q02`, `marketplace_qna_zh_cn_15_q03`, `marketplace_qna_zh_cn_15_q04`, `marketplace_qna_zh_cn_15_q05`, `marketplace_qna_zh_cn_15_q06`, `marketplace_qna_zh_cn_15_q07`, `marketplace_qna_zh_cn_15_q08`, `marketplace_qna_zh_cn_15_q09`, `marketplace_qna_zh_cn_15_q10`, `marketplace_qna_zh_cn_15_q11`, `marketplace_qna_zh_cn_15_q12`, `marketplace_qna_zh_cn_15_q13`, `marketplace_qna_zh_cn_15_q14`, `marketplace_qna_zh_cn_15_q15`, `marketplace_qna_zh_cn_15_q16`, `marketplace_qna_zh_cn_15_q17`, `marketplace_qna_zh_cn_15_q18` |
| `marketplace_qna_zh_cn_16` | 11 | `marketplace_qna_zh_cn_16_q01`, `marketplace_qna_zh_cn_16_q02`, `marketplace_qna_zh_cn_16_q03`, `marketplace_qna_zh_cn_16_q04`, `marketplace_qna_zh_cn_16_q05`, `marketplace_qna_zh_cn_16_q06`, `marketplace_qna_zh_cn_16_q07`, `marketplace_qna_zh_cn_16_q08`, `marketplace_qna_zh_cn_16_q09`, `marketplace_qna_zh_cn_16_q10`, `marketplace_qna_zh_cn_16_q11` |

## Evaluation Notes

- The Chinese and English documents mirror the same subjects. Same-language metadata filtering is part of the intended retrieval contract and prevents equivalent translations from competing for rank.
- The Golden Query audit emits a 248-row structural-anchor map for every bilingual query targeting documents 02, 06, 08, and 10-16. Each row records `query id -> expected document -> matching Q&A section heading -> answer lines`, providing the per-query anchor audit for the deterministic retrieval-disambiguation pass.
- The final convergence pass is trim-first: repeated Governance and Consumer concepts are condensed across documents 12-16, document 14 contains no `My Shares` balance-display language, and bilingual q15_q13 remains assigned to document 15. The en_08_q04 and zh_cn_11_q19 source answers are unchanged pending an owner decision on embedding-drift waivers.
- Chat fact checks use OR alternatives inside a required fact group and require every group. This accepts normal paraphrases without accepting missing concepts.
- The share-sale chat cases explicitly request both branches: DEX trading when a pair exists and Redeem when it does not. This removes model-composition ambiguity while preserving the source question's meaning.
- Live evidence stores only bounded answer previews and redacts runtime admin, Marketplace user, wallet, and bearer values.

## Acceptance Evidence

Final acceptance is determined by:

```bash
.venv/bin/python -m tests.rag_eval.marketplace_qna_acceptance_validator
.venv/bin/python -m tests.rag_eval.marketplace_qna_acceptance_status \\
  --output .artifacts/release/marketplace_qna_acceptance_status.json
```

The repeatable operational procedure is documented in `docs/MARKETPLACE_QNA_RAG_INGESTION_RUNBOOK.md`.
