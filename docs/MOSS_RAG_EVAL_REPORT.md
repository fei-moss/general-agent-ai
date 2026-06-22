# MOSS RAG Eval Report

## Run Summary

- Date: 2026-06-17
- Spec: `SPEC-RAG-EVAL-001`
- Persistent DockerHost environment: `chris-general-agent-ai-rag`
- API URL: `https://api-chris-general-agent-ai-rag.dkhost.vixmk-yo.org`
- Knowledge base id: `kb_moss_wiki_v1`
- Owner user id: `rag_eval_operator`
- Embedding provider: `gemini`
- Embedding model: `gemini-embedding-2`
- Embedding dimension: `256`
- Vector store: DockerHost PostgreSQL with pgvector

## Dataset Scope

The reviewed MOSS Wiki seed now covers the P0-P2 import set from the canonical
English GitBook markdown index. Chinese and Korean translated pages are excluded
from this seed to avoid duplicate retrieval noise; Chinese, English, and mixed
Golden Queries still verify cross-language retrieval behavior.

| Dataset | Count |
|---|---:|
| Corpus documents | 40 |
| Golden Queries | 79 |
| Reviewed query rows | 79 |
| Capability groups | 10 |
| Multi-source queries | 15 |

Source of truth:

- `tests/rag_eval/moss_rag_seed_manifest.json`
- `tests/rag_eval/moss_corpus.jsonl`
- `tests/rag_eval/moss_golden_queries.jsonl`
- `tests/rag_eval/moss_golden_query_review.jsonl`

## Persistent Ingestion Result

Artifact: `.artifacts/release/moss_rag_ingestion_summary.json`

| Metric | Value |
|---|---:|
| Submitted documents | 40 |
| Persisted documents | 40 |
| Succeeded ingestion jobs | 40 |
| Failed ingestion jobs | 0 |
| Persisted chunks | 44 |
| Distinct source doc ids | 40 |
| Gemini embedding chunks | 44 |

Smoke query:

| Query | Top matched source doc | Score |
|---|---|---:|
| MOSS Agent 会动用真实资金吗？ | `moss_product_safety` | 0.7544515132904053 |

Top 5 smoke matches:

| Rank | Source doc id | Score |
|---:|---|---:|
| 1 | `moss_product_safety` | 0.7544515132904053 |
| 2 | `moss_faq_general_core` | 0.7412479807434111 |
| 3 | `moss_agent_arena_competitions` | 0.7192860841751099 |
| 4 | `moss_about_platform` | 0.7179825779769765 |
| 5 | `moss_hosted_agent_creation` | 0.7175973822118424 |

## Golden Query Eval Result

Artifact: `.artifacts/release/moss_rag_promptfoo_eval.json`

| Metric | Value |
|---|---:|
| Golden Queries | 79 |
| Passed | 79 |
| Failed | 0 |
| Errors | 0 |
| Pass rate | 100% |
| Eval duration | 61.797s |

Matched-rank distribution:

| Matched rank | Queries |
|---:|---:|
| 1 | 63 |
| 2 | 11 |
| 3 | 5 |

Representative retrieval checks:

| Query | Matched doc id | Rank |
|---|---|---:|
| MOSS Agent 会动用真实资金或收取真实手续费吗？ | `moss_product_safety` | 1 |
| MOSS 的 AI 能访问哪些数据，是否能直接操作我的外部账户？ | `moss_product_safety` | 2 |
| Live Mode 和 Hell Mode 上排行榜的时间有什么不同？ | `moss_leaderboards_modes` | 1 |
| Hell Mode 使用哪段历史行情做压力测试回测？ | `moss_leaderboards_modes` | 2 |
| Agent 详情页如何查看净敞口、胜率和交易历史？ | `moss_agent_detail_metrics` | 1 |
| 写 MOSS 策略 Prompt 时必须包含哪些关键要素？ | `moss_strategy_prompt_config` | 1 |
| ATR 和 sl_atr_mult 在 Moss 策略里是什么意思？ | `moss_key_metrics_risk` | 1 |
| Multi-Agent Portfolio 为什么能降低单一策略风险？ | `moss_advanced_strategy_techniques` | 1 |

## Acceptance Evidence

- Gemini preflight: passed, HTTP 200, 256-dimensional embedding.
- Golden Query audit: passed, 40 corpus docs and 79 reviewed Golden Queries.
- MOSS semantic Promptfoo eval: passed, 79/79.
- Persistent ingestion summary: passed, 40 documents and 44 Gemini chunks in pgvector.
- Smoke query: non-degraded and matched `moss_product_safety`.

Commands used for evidence:

```bash
.venv/bin/python -m tests.rag_eval.moss_gemini_preflight \
  --output .artifacts/release/moss_gemini_preflight.json

.venv/bin/python -m tests.rag_eval.moss_golden_query_audit \
  --output .artifacts/release/moss_golden_query_audit.json

PROMPTFOO_PYTHON=.venv/bin/python npx --yes promptfoo@latest eval \
  -c tests/rag_eval/moss_promptfooconfig.yaml \
  --no-cache \
  --output .artifacts/release/moss_rag_promptfoo_eval.json

.venv/bin/python -m tests.rag_eval.moss_acceptance_validator
```

## Notes

- The semantic eval uses Gemini embeddings against the reviewed MOSS corpus in
  process. Persistent pgvector correctness is covered separately by the
  DockerHost ingestion summary and smoke query.
- The previous 12-document / 21-query seed has been superseded by
  `moss-wiki-rag-seed-v2`.
