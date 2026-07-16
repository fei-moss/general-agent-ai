# Marketplace QnA Golden Queries Review

## Scope

This review is the human-readable evidence for `SPEC-RAG-EVAL-002`. The seed is an exact in-repository copy of 9 Chinese and 9 English Marketplace QnA Markdown files. It covers 114 source questions with one same-language semantic retrieval case per question and 18 representative end-to-end chat cases.

Machine-readable authorities:

- `tests/rag_eval/marketplace_qna_rag_seed_manifest.json`
- `tests/rag_eval/marketplace_qna_coverage_contract.json`
- `tests/rag_eval/marketplace_qna_acceptance_evidence_contract.json`
- `tests/rag_eval/marketplace_qna_golden_query_review.jsonl`
- `tests/rag_eval/marketplace_qna_chat_cases.jsonl`

## Review Conclusion

The fixture family has complete source-question coverage: 18 documents, 114 Golden Queries, 114 review rows, and 18 chat cases. Chinese and English each contribute 57 retrieval cases. Every case points to exactly one expected source document and a source answer line range.

The current acceptance target is deliberately strict:

- local Promptfoo: 114/114 top-5, zero degraded, Top-1 at least 80%;
- DockerHost `/rag/query`: 114/114 top-5 with the same language filter, zero degraded, Top-1 at least 80%;
- live chat: 18/18 terminal `SUCCEEDED`, server-default knowledge base, RAG start/finish evidence, all required fact groups, no forbidden claims;
- persistent ingestion: 18 documents, 18 successful jobs, 141 chunks, zero failed jobs, exact source-hash equality.

## Corpus Quality Finding

### CORPUS-MPQNA-001 — Tool-built versus template-deployed Agent answer is underspecified

Source: `tests/rag_eval/marketplace_qna_sources/zh-CN/08_安全与风险.md:43-45`.

The question asks whether Tool-built and official/template-deployed Agents differ in trustworthiness and risk. The answer only says they are different layers: Tool provides the trading strategy, while template deployment provides an on-chain fundraising channel. It does not explicitly answer how to assess trust or risk, and it contains little of the question's trust/risk vocabulary.

Observed effect: a natural paraphrase and even the original question were outranked by documents about Discover, Tool, deployment, and fundraising. Adding the natural topic scope “Moss 安全与风险” retrieved the intended document at rank 1. This indicates a source specificity/structure weakness, not a pgvector, embedding, chunking, or language-filter defect.

Recommended content revision for the content owner:

> Tool 自建和模板部署解决的是不同层面的问题。Tool 是策略创建与执行层；模板部署是链上募集资金和份额管理渠道。无论采用哪种方式，都不代表官方背书或风险保证。判断可信度与风险时，应结合链上记录、创建者披露、合约参数、历史交易表现和风险控制措施，而不能只看“Tool 自建”或“模板部署”标签。

Also consider giving this Q&A its own subheading or cross-linking it to the Discover evaluation criteria. The item is a recommended corpus correction; it does not block the present acceptance because the reviewed contextual case is source-grounded and the complete suite meets the declared thresholds.

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
| `marketplace_qna_zh_cn_01` | 5 | `marketplace_qna_zh_cn_01_q01`, `marketplace_qna_zh_cn_01_q02`, `marketplace_qna_zh_cn_01_q03`, `marketplace_qna_zh_cn_01_q04`, `marketplace_qna_zh_cn_01_q05` |
| `marketplace_qna_zh_cn_02` | 7 | `marketplace_qna_zh_cn_02_q01`, `marketplace_qna_zh_cn_02_q02`, `marketplace_qna_zh_cn_02_q03`, `marketplace_qna_zh_cn_02_q04`, `marketplace_qna_zh_cn_02_q05`, `marketplace_qna_zh_cn_02_q06`, `marketplace_qna_zh_cn_02_q07` |
| `marketplace_qna_zh_cn_03` | 2 | `marketplace_qna_zh_cn_03_q01`, `marketplace_qna_zh_cn_03_q02` |
| `marketplace_qna_zh_cn_04` | 16 | `marketplace_qna_zh_cn_04_q01`, `marketplace_qna_zh_cn_04_q02`, `marketplace_qna_zh_cn_04_q03`, `marketplace_qna_zh_cn_04_q04`, `marketplace_qna_zh_cn_04_q05`, `marketplace_qna_zh_cn_04_q06`, `marketplace_qna_zh_cn_04_q07`, `marketplace_qna_zh_cn_04_q08`, `marketplace_qna_zh_cn_04_q09`, `marketplace_qna_zh_cn_04_q10`, `marketplace_qna_zh_cn_04_q11`, `marketplace_qna_zh_cn_04_q12`, `marketplace_qna_zh_cn_04_q13`, `marketplace_qna_zh_cn_04_q14`, `marketplace_qna_zh_cn_04_q15`, `marketplace_qna_zh_cn_04_q16` |
| `marketplace_qna_zh_cn_05` | 4 | `marketplace_qna_zh_cn_05_q01`, `marketplace_qna_zh_cn_05_q02`, `marketplace_qna_zh_cn_05_q03`, `marketplace_qna_zh_cn_05_q04` |
| `marketplace_qna_zh_cn_06` | 9 | `marketplace_qna_zh_cn_06_q01`, `marketplace_qna_zh_cn_06_q02`, `marketplace_qna_zh_cn_06_q03`, `marketplace_qna_zh_cn_06_q04`, `marketplace_qna_zh_cn_06_q05`, `marketplace_qna_zh_cn_06_q06`, `marketplace_qna_zh_cn_06_q07`, `marketplace_qna_zh_cn_06_q08`, `marketplace_qna_zh_cn_06_q09` |
| `marketplace_qna_zh_cn_07` | 4 | `marketplace_qna_zh_cn_07_q01`, `marketplace_qna_zh_cn_07_q02`, `marketplace_qna_zh_cn_07_q03`, `marketplace_qna_zh_cn_07_q04` |
| `marketplace_qna_zh_cn_08` | 7 | `marketplace_qna_zh_cn_08_q01`, `marketplace_qna_zh_cn_08_q02`, `marketplace_qna_zh_cn_08_q03`, `marketplace_qna_zh_cn_08_q04`, `marketplace_qna_zh_cn_08_q05`, `marketplace_qna_zh_cn_08_q06`, `marketplace_qna_zh_cn_08_q07` |
| `marketplace_qna_zh_cn_09` | 3 | `marketplace_qna_zh_cn_09_q01`, `marketplace_qna_zh_cn_09_q02`, `marketplace_qna_zh_cn_09_q03` |

## Evaluation Notes

- The Chinese and English documents mirror the same subjects. Same-language metadata filtering is part of the intended retrieval contract and prevents equivalent translations from competing for rank.
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

