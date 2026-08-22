---
spec_id: SPEC-CONSUMER-GOLDEN-ANSWERS-001
module: consumer_golden_answers
status: implemented
workflow_class: HARNESS-SPEC-FIRST-FEATURE
---

# Consumer Golden Answers

## Specification

### Source And Scope

- Product-owner-approved source batch dated 2026-08-19 is vendored verbatim at
  `tests/chat_eval/fixtures/consumer_pixverse_golden_source_20260819.md`, with
  SHA-256
  `4715696ebba1c743eff0f762ad6e6848f0d513b670c4eb53ba3473dc4149450b`.
  It was originally delivered at
  `/private/tmp/claude-501/-Users-renfei-Documents-GitHub/d813e659-4174-41fd-a7ad-d6a4cc302f68/scratchpad/consumer-pixverse-golden-source-20260819.md`.
  The adapter preserves the supplied question and ideal-answer text; the
  vendored fixture is the durable provenance authority and is not runtime data.
- The batch contains 48 generic Redemption questions and 18 PixVerse-specific
  questions. It is Chinese-only. English translation and English Golden Cases
  are outside this batch and require later product-owner approval.
- Eight supplied questions are not approved executable cases and are emitted as
  intake blockers rather than silently dropped:
  - `兑换码去哪里看？`: the supplied answer is a tester bug note
    (`这个目前测试的时候，找不到地方点击回查看兑换码`), not an ideal answer.
  - `兑换码丢了怎么办？`: the supplied ideal answer is empty.
  - `兑换码可以给别人用吗？`: the supplied ideal answer is empty.
  - `赎回之后已经拿到的兑换码还能用吗？`: the supplied ideal answer is empty.
  - `赎回要收费吗？`: the supplied ideal answer is empty.
  - `持有份额有额外收益吗？`: the supplied ideal answer is empty.
  - `持有越久越好吗？`: the supplied ideal answer is empty.
  - `兑换码多久过期？`: the supplied ideal answer is empty.
- The remaining 58 questions are an incremental approved regression batch, not
  an exhaustive statement of Consumer, Redemption, PixVerse, or Marketplace
  behavior.
- The product-owner Rave Governance Agent source dated 2026-08-21 is vendored
  verbatim at
  `tests/chat_eval/fixtures/rave_governance_golden_source_20260821.md`, with
  SHA-256
  `47c20ff3f536263f34089b20e7e72006c4f61300d6d1a543db6ffc162d2b0eb5`.
  It contains 43 supplied Q&As. Four answers are literal
  `【按实际规则填】` blanks and remain pending owner input: treatment of accrued
  rewards on early redemption, lock period, redemption wait time, and partial
  redemption support.

### Behavior

- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R1`: every emitted case applies only to
  Agent type `consumer`. A run against any other Agent type is
  `not_applicable`, mirroring the Ballot Golden Case scope contract; it is not a
  product defect, hard failure, semantic gap, or release blocker.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R2`: each approved source question and ideal
  answer is preserved without rewriting. The known `怎么开始？` answer line
  whose label is a bare `：` is accepted as the answer. Normalized rows retain
  Chinese locale, stable source/order identity, area, risk, required stable fact
  groups, affirmative forbidden claims, placeholders, dynamic rules, Agent
  scope, and tags.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R3`: the eight exclusions remain explicit
  intake blockers. Adapter CLI output includes every blocker and exits with
  status 1 while still writing all otherwise valid rows for review.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R4`: PixVerse-specific part-two cases
  additionally apply only when typed Marketplace `ai-context` Agent identity
  fields, including `agent.name` or `agent.description`, identify the brand as
  PixVerse. The regression contract never hardcodes an Agent ID, contract
  address, wallet, or deployment address. Other Consumer brands make those
  cases `not_applicable`.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R5`: values represented by `【...】`
  placeholders are dynamic facts. They include brand, minimum Mint amount,
  redemption threshold, Mint fee, Refund fee, accepted settlement token,
  redemption benefit/value/entry/expiry/feature scope, price comparison,
  enterprise eligibility, official support/community channels, and support
  email. Deterministic rules include Chinese and source-language matching terms
  such as `门槛`/`Threshold`, `铸造费`/`Mint fee`, `赎回费`/`Refund fee`,
  `结算代币`/`Accept Token`, `最低金额`, `品牌方`, `权益`, `兑换码价值`,
  `有效期`, and `支持渠道`. A provided dynamic fact is expressed when the answer
  states the actual typed value. The brand-name rule uses one OR group containing
  the typed brand value and the generic brand terms because the approved ideal
  answers themselves use `品牌方`; therefore either `PixVerse` or `品牌方`
  satisfies that fact. The accepted-token rule is value-only: the typed symbol
  such as `bnbUSDC` satisfies it, while `结算代币` alone does not. Absent facts
  remain preflight blockers rather than receiving placeholder or
  unavailable-value substitutes.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R6`: dynamic target truth is derived only
  from the target Agent's typed Marketplace `ai-context`. A case declaring a
  dynamic rule is `blocked`, not invented, passed, or failed, when that rule's
  target truth is absent, mirroring
  `SPEC-HYPERLIQUID-GOLDEN-ANSWERS-001-R3`. Current Consumer Agents have no
  daily-report registry, and redemption configuration, threshold, and benefit
  data live in an external Consumer backend that is not returned by
  `ai-context`; blocking on those missing facts is therefore the expected
  current preflight result.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R7`: the lossless adapter feeds the existing
  approved Golden Case `ingest`, `target-truth`, `preflight`, and `report`
  contract. It does not create a parallel ingestion or evaluation workflow.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R8`: affirmative statements contradicted by
  the approved answers are deterministic forbidden claims, including claims
  that the product is an investment or NFT, Mint directly yields a code,
  already-redeemed shares remain refundable, a brand or Moss can move
  principal, annualized yield exists, PixVerse is issuing a token, or shares
  represent PixVerse equity or valuation.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R9`: stable Consumer/Redemption and PixVerse
  mechanisms come from the bilingual, versioned Marketplace QnA corpus. The
  corpus explains fixed mechanisms and directs Agent-specific thresholds,
  amounts, fee rates, code details, entry points, support routes, identity,
  addresses, and network values to the current Agent page or typed context. It
  never hardcodes an Agent ID, address, target-specific value, or an answer for
  any of the eight owner-excluded questions.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R10`: the V8 QnA knowledge base is imported
  as a blue-green version and selected only after ingestion, semantic
  retrieval, live chat, and release acceptance pass. The prior knowledge base
  remains retained and selectable for rollback.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R11`: V7 revises wording in the bilingual
  V6 documents 06, 10, 11, and 12 only to disambiguate retrieval. The revised
  anchors distinguish template/chain selection, Governance proposal snapshots
  and vote incentives, Trading Agent Mint settlement and batch redemption
  claiming, and the project benefits of launching a Governance Agent. Their
  factual claims and Golden Query expectations are unchanged.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R12`: after a second live retrieval replay,
  V7 adds structural query-to-section anchors across bilingual documents 02,
  06, 08, and 10-16. The additional V6 revisions partition Marketplace listing
  eligibility, launch immutability, geographic restrictions, Governance
  holder mechanics, Governance product behavior, and Trading Agent settlement;
  they change retrieval wording only, with unchanged semantics and unchanged
  V6 Golden Query expectations. The Golden Query audit emits the complete
  query-to-document, section-heading, and answer-line mapping for this set.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R13`: the final V7 corpus pass removes
  redundant retrieval-attractor wording from bilingual documents 06 and
  12-16 instead of adding further topical prose. It preserves all V6 Golden
  Queries and facts, keeps the previously rescued 06/10/12 anchors, and assigns
  Consumer balance-display semantics to document 15 while document 14 contains
  only code-redemption actions. The English geographic-restriction case and
  Chinese Trading Agent Mint-delay case remain unchanged as owner-reviewed
  embedding-drift waiver candidates.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R14`: V8 adds exactly one bilingual Rave
  Governance Agent document pair at order 17. It contains only Rave-specific
  approved facts and one compact cross-reference to shared documents
  04/10/11/12. Every new retrieval question names Rave, RaveDAO, or vRAVE so
  existing generic Governance Golden Queries remain assigned to documents
  10/12.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R15`: stable numeric facts are confined to
  the Rave document pair: the fixed reward rate, per-account cap, and proposal
  pass threshold each appear once per language. Fee rates, voting entry,
  proposal deadline, contract address, and network remain current-page,
  proposal-page, or typed-context facts. The four blank owner answers are
  explicitly unspecified and never receive inferred defaults.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R16`: Marketplace and MOSS evaluation and
  ingestion contracts use Gemini `gemini-embedding-2` at dimension 1536. V8
  requires `EMBEDDING_DIM=1536` explicitly on every deploy because the runtime
  default remains 256, plus a full re-ingest into a new knowledge base. An
  old-dimension knowledge base degrades while the server produces
  1536-dimensional query vectors; promotion and rollback therefore change
  `EMBEDDING_DIM` and `RAG_DEFAULT_KNOWLEDGE_BASE_ID` as one coordinated pair.
  The previous 316-query `301/316` and Top-1 `80.4%` measurements remain
  historical 256-dimensional evidence and require a 1536-dimensional
  re-baseline.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R17`: owner approval
  `owner-request:rave-kb-v8-1536-20260821` changes the pgvector column from
  `vector(256)` to dimensionless `vector` through migration
  `20260821_001_rag_embedding_dimensionless`, after first dropping the
  dimension-typed HNSW index. The migration preserves retained 256-dimensional
  chunks. Fresh installs use the same dimensionless schema. Application checks
  enforce the active embedding dimension, each knowledge base remains
  dimension-uniform, and retrieval filters by `knowledge_base_id` before
  distance comparison, allowing old and new dimensions in different knowledge
  bases. Sequential scan is accepted at the current corpus scale; a
  dimension-typed ANN strategy is deferred to a future scale change.

### V8 Owner-Mandated Dedup Decision Table

| Owner question | Disposition |
| --- | --- |
| 这个 agent 是做什么的？ | New document 17, Rave purpose anchor |
| vRAVE 是什么？ | New document 17, vRAVE definition anchor |
| 和直接持有 $RAVE 有什么区别？ | New document 17, Rave-specific comparison |
| 这是投资产品吗？ | Shared document 04 product/risk framing; not repeated in 17 |
| 这是 RaveDAO 发的吗？ | New document 17, Moss/RaveDAO partnership |
| 怎么开始？ | Shared documents 04/11 Mint and settlement flow; not repeated in 17 |
| 最少要 mint 多少？ | New document 17, combined Mint-limits anchor |
| 有上限吗？ | New document 17, combined Mint-limits anchor |
| 为什么设上限？ | New document 17, combined anti-concentration rationale |
| mint 之后马上能投票吗？ | New document 17, Rave settlement-plus-Claim eligibility |
| mint 要收费吗？ | New document 17 dynamic-fields anchor; current page only |
| 可以用别的币 mint 吗？ | New document 17, contract-fixed $RAVE token |
| 可以分多次 mint 吗？ | New document 17, combined Mint-limits anchor |
| 怎么投票？ | New document 17 dynamic-fields anchor; current Agent page or typed context |
| 投票权怎么算？ | New document 17, vRAVE-balance rule |
| 一个提案怎么才算通过？ | New document 17, RaveDAO threshold rule |
| 任意金额都能投票吗？ | New document 17, combined voting-weight anchor |
| 不投票会怎样？ | New document 17, combined holder-control anchor |
| 自己投还是 agent 代投？ | New document 17, combined holder-control anchor |
| 投票之后可以赎回吗？ | Strengthened shared document 10 post-vote Redeem rule |
| 投票有截止时间吗？ | New document 17 dynamic-fields anchor; proposal page only |
| 6% 是什么意思？ | New document 17, combined Rave reward anchor |
| 6% 会变吗？ | Strengthened shared document 10 existing-holder terms |
| 奖励什么时候到手？ | New document 17, combined Rave reward anchor |
| 中途赎回，已累积奖励还有吗？ | Pending owner; document 17 explicitly marks unspecified |
| 为什么不能随时提取奖励？ | New document 17, combined Rave reward rationale |
| 这算理财产品吗？ | Shared document 04 product/risk framing; not repeated in 17 |
| 钻石有什么用？ | New document 17, combined Diamonds anchor |
| 钻石和 6% 奖励冲突吗？ | New document 17, combined Diamonds anchor |
| 怎么把 $RAVE 拿回来？ | Shared document 12 Request Redeem flow; not repeated in 17 |
| 有锁定期吗？ | Pending owner; document 17 explicitly marks unspecified |
| 赎回也要等吗？ | Pending owner; document 17 explicitly marks unspecified |
| 赎回之后投票权还在吗？ | Strengthened shared document 10 burn/voting-power rule |
| 可以只赎回一部分吗？ | Pending owner; document 17 explicitly marks unspecified |
| 赎回要收费吗？ | New document 17 dynamic-fields anchor; current page only |
| 我的 $RAVE 在谁那里？ | Shared document 10 contract-custody rule; not repeated in 17 |
| 规则会不会中途改？ | Strengthened shared document 10 existing-holder terms |
| 我怎么验证？ | New document 17, onchain-verification anchor |
| vRAVE 可以转给别人吗？ | New document 17, non-transferability anchor |
| vRAVE 会涨价吗？ | New document 17, backing/value-boundary anchor |
| 6% 是浮动的吗？ | New document 17 reward anchor plus shared document 10 immutability rule |
| 可以一边投票一边把钱拿回来吗？ | Strengthened shared document 10 burn/voting-power rule |
| 这是保本的吗？ | New document 17, $RAVE-denominated mechanism and market-price boundary |

### Invariants

- No approved question, ideal answer, placeholder value, target Agent identity,
  or address is copied into runtime Prompt assembly or product behavior.
- Missing Consumer backend or Marketplace data never becomes an example,
  default, inferred value, successful fact check, or fabricated daily report.
- Current-Agent identity, threshold, amount, fee, code, entry, support, address,
  or network values are never copied into the fixed QnA corpus.
- Application changes are limited to the typed consumer dynamic-field registry
  constant authorized by `owner-request:consumer-golden-regression-20260819`
  and the dimensionless pgvector schema migration authorized by
  `owner-request:rave-kb-v8-1536-20260821`.
- Runtime Prompt assembly, tools, validators, orchestration, Go Marketplace
  code, and API behavior are unchanged. The persistence schema becomes
  dimensionless while environment templates, DockerHost defaults, evaluation
  fixtures, and operator guidance use embedding dimension 1536.
- No Mint, Refund, Redeem, code generation, signature, wallet write, payment,
  trade, or other mutating action is introduced by this regression harness.

### Compatibility And Rollback

- Existing approved cases without brand scope retain their previous behavior.
  Existing Agent-type and dynamic-fact contracts remain compatible.
- V8 rollback restores both `EMBEDDING_DIM` and
  `RAG_DEFAULT_KNOWLEDGE_BASE_ID` to values matching the retained prior
  knowledge base; neither knowledge base is deleted. The forward DDL migration
  remains applied because its dimensionless column preserves and can query the
  retained 256-dimensional chunks after the coordinated runtime rollback.

## Implementation Plan

1. Add RED tests for the bare-colon source quirk, eight explicit exclusion
   blockers and CLI status, placeholder extraction, PixVerse brand scope,
   existing-workflow ingestion, and absent Consumer dynamic truth.
2. Add the lossless Consumer/PixVerse adapter with stable CN IDs, handcrafted
   fact groups, forbidden claims, dynamic mappings, and tags.
3. Register Consumer dynamic rules and typed target-truth extraction in the
   existing approved Golden Case workflow. Derive PixVerse brand scope from
   typed Agent name/description and leave unavailable external facts absent so
   preflight blocks.
4. Register this spec, run the focused RED-to-GREEN suite, then run full pytest
   and both requested spec checks without changing runtime behavior.
5. Keep the complete approved source as a hash-pinned test fixture and assert
   all 58 emitted rows match every static required group and trigger none of
   their own forbidden claims under the production evaluator helpers.
6. Add bilingual Consumer/Mint, code-redemption, Refund/custody/UI, and PixVerse
   QnA documents; extend one-query-per-question review evidence and one
   representative chat case per document; compile and hash-pin the V7 seed.
7. Add a RED report-level regression for brand generic/value alternatives and
   accepted-token value-only matching, then keep existing Ballot and
   Hyperliquid dynamic behavior green.
8. After a live V7 retrieval replay exposes semantic near-ties, narrow the
   bilingual 13-16 topic boundaries, replace V7-authored meta queries with
   realistic user questions, and sharpen the bilingual V6 06/10/11/12 wording
   without changing its semantics or Golden Query expectations.
9. After the second deterministic replay exposes neighboring-document flips,
   give every Golden Query for bilingual documents 06, 08, and 10-16 a direct
   Q&A anchor, add the same structural protection to the newly affected
   document 02, hard-partition the competing topics, and publish the complete
   248-query anchor mapping in the deterministic audit artifact.
10. For the final convergence pass, condense repeated Governance, Consumer,
    code-redemption, Refund, and PixVerse prose; remove sibling timing,
    payment-token, custody, batch-claim, and balance-display attractors; retain
    document 15 as the bilingual owner of `My Shares` balance semantics; and
    leave the two owner waiver candidates unchanged.
11. Add RED regressions for the hash-pinned Rave owner fixture, bilingual Rave
    document boundary, pending-owner topics, dedup ownership, V8 counts, and
    dimension 1536 contracts.
12. Add the order-17 bilingual Rave pair, strengthen shared document 10 where
    the owner supplied generic Redeem/immutability precision, and add one
    Rave-specific semantic query plus review evidence for every new Q&A and one
    representative chat case per language.
13. Rebuild and hash-pin V8 fixtures, record the deterministic production chunk
    count, update operational dimension migration/rollback guidance, and run
    focused plus full repository verification without upload or deployment.
14. Add RED schema-contract tests, migrate the chunk embedding column to
    dimensionless pgvector without rewriting existing rows, remove the typed
    HNSW index from migrated and fresh schemas, cover mixed-dimension
    knowledge-base isolation, and document failed-import cleanup before the V8
    retry.

## Closeout Evidence

- The source adapter emits 58 Chinese rows: 40 generic Redemption cases and 18
  PixVerse cases. Stable IDs retain original per-section ordering, including
  gaps for excluded Redemption questions, and all eight exclusions are present
  in the blocker report. The full-batch regression parses the durable vendored
  source and verifies its delivery hash.
- The focused Consumer adapter/workflow tests pass after first failing on the
  absent Consumer implementation. Existing approved Golden workflow,
  evaluator, and Marketplace client regression tests remain green.
- Consumer target truth exposes only typed facts currently present, including
  accepted token and PixVerse identity when supplied by Agent name/description.
  Missing minimum amount, threshold, fee, benefit, expiry, and support facts
  remain absent and block applicable preflight cases.
- Marketplace QnA V7 contains 32 bilingual documents and 316 reviewed Golden
  Queries, including four new authoritative Chinese Consumer/PixVerse topics
  and four faithful English translations. It compiles to 289 chunks with 32
  representative chat cases; the V6 knowledge base remains the rollback target.
- The V7 retrieval-disambiguation revision gives Consumer onboarding, code
  redemption, Refund/UI, and PixVerse partnership facts distinct bilingual
  anchors. It also sharpens the V6 06/10/11/12 near-ties while retaining every
  V6 Golden Query and all existing factual claims.
- The second retrieval-disambiguation revision structurally anchors all 248
  Golden Queries for bilingual documents 02, 06, 08, and 10-16. The generated
  audit records each query ID's expected document, matching Q&A heading, source
  path, and answer lines; the further V6 edits remain wording-only and preserve
  their factual meaning and Golden Query expectations.
- The final trim removes repeated concepts across overlapping chunks while
  retaining every required fact. Governance product comparison stays in 12,
  holder mechanics stay in 10, Consumer Mint flow stays in 13, code actions
  stay in 14, and Consumer custody/balance/UI stays in 15. The q15_q13 cases
  remain assigned to bilingual document 15; no Golden Query reassignment is
  required.
- The evaluator regression proves `品牌方` and `PixVerse` both satisfy the
  available brand fact, `bnbUSDC` satisfies the accepted-token fact, and
  `结算代币` alone does not. Existing Ballot and Hyperliquid dynamic-fact tests
  remain unchanged and green.
- Live-baseline evidence broadened fact-group alternatives only for
  paraphrase-equivalent wording; the asserted semantics are unchanged.
  A second pass against the V8@1536 recording reaches 14/43 hard passes while
  preserving the V7 recording at 16/43; the asserted semantics remain unchanged.
- Marketplace QnA V8 contains 34 bilingual documents and 350 reviewed Golden
  Queries. The new Rave pair contributes 17 questions per language and one
  representative chat case per language; all Rave retrieval questions are
  scoped by Rave, RaveDAO, or vRAVE terminology. The production chunker emits
  313 chunks at size 400 and overlap 80.
- The four owner blanks remain one explicit pending-owner Q&A per language.
  Fees, voting entry, proposal deadline, contract address, and network remain
  dynamic. Generic product framing, custody, Mint/Redeem flow, and post-vote
  share-burning semantics remain owned by the existing shared documents.
- Evaluation/ingestion manifests, preflight, Promptfoo configs, environment
  guidance, and operator runbooks use dimension 1536. Migration
  `20260821_001_rag_embedding_dimensionless` and fresh-install SQL use an
  untyped pgvector column with no fixed-dimension HNSW index, preserving the
  retained 256-dimensional knowledge bases for rollback.
- Final local verification passes the focused Marketplace/Promptfoo/Consumer/
  Rave suites, full pytest (with one pre-existing skip), the legacy spec
  contract, the production deployment contract, Golden Query audit, and
  `git diff --check`. The spec-registry check was attempted but could not fetch
  `harnessctl` because sandbox DNS could not resolve `proxy.golang.org`. No live
  replay, upload, deployment, or product/runtime acceptance is claimed.
