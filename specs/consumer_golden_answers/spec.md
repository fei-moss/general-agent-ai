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
  Consumer refund claims in this historical batch are superseded by the
  2026-09-16 owner directive below; preservation does not make them current
  product truth.
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
- The remaining 58 questions are a historically approved regression batch, not
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

### V9 Owner-Directed Semantic Reversal (2026-09-16)

- The owner directive dated 2026-09-16 explicitly changes Consumer behavior:

  > 消费类不支持Refund，请检查页面上的所有 Agent 信息之后再决定是否Mint

  Its source is the owner-supplied
  `consumer-no-refund-owner-directive-20260916.md`; this quotation records its
  authority durably. This is an intentional semantic reversal, not retrieval
  wording cleanup. It overrides conflicting Consumer claims in V7/V8 and the
  preserved 2026-08-19 golden source. It applies to all Consumer-type Agents,
  including the current Model Max and PixVerse brands, without hardcoding
  current Agent IDs or branding into generic corpus content.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R18`: source set
  `marketplace-qna-bilingual-2026-09-16-v9` updates bilingual documents 13-16
  and their generated corpus, Golden Queries, review evidence, chat cases,
  manifest hashes, and reviewed seed counts. Document 03 changes only if it
  promises Consumer refundability. Documents 04/07/08/10/11/12/17 retain their
  Trading/Governance Refund/Redeem semantics without modification.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R19`: document 15 replaces all Consumer
  Refund mechanism Q&As with one clear no-Refund Q&A using the owner's exact
  Chinese wording and a faithful English translation. Remove eligibility,
  amount, Pending-to-Claimable flow, count-limit, grey Refund-button,
  code-versus-Refund choice, and refund-value-based principal-protection
  explanations. Retain smart-contract custody, `My Shares` display semantics,
  masked-address Mint/code activity records, and page-state-based
  `Paused by owner` explanations for Mint/operations; do not invent pause
  specifics. If a brand stops honoring benefits, unredeemed-share assets remain
  held by the contract, and use of issued codes depends on brand fulfillment.
  Do not promise principal recovery or introduce an alternative exit mechanism.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R20`: document 14 says remaining shares
  continue to be held by the user after partial code redemption. Consumed
  shares cannot be restored. Preserve the active `去兑换` flow, quantity and
  threshold requirements, `去消费` jump, failure recording/retry/support, and
  no-auto-redemption behavior. Document 13 removes all refundability selling
  points and instead tells the user to review all Agent information before
  Mint; its non-investment/no-APY framing does not rely on a refund value.
  Document 16's partnership-termination answer distinguishes contract custody
  of unredeemed-share assets from PixVerse fulfillment/terms for issued codes;
  code-to-wallet mapping and account requirements remain unchanged.
- Rename the bilingual document-15 files to
  `15_资金安全与界面状态.md` and `15_Fund-Safety-and-UI-States.md`.
  The shorter titles reflect the retained custody/UI topics and avoid
  advertising an unavailable Refund mechanism. Update source paths, filename
  metadata, builder references, and manifest entries consistently while
  preserving logical document order/identity.
- The verbatim Consumer source fixture, adapter, regression harness, and eight
  existing intake blockers remain unchanged. V9 does not add per-case
  exclusions, annotations, or substitute ideal answers. The affected source
  cases are recorded below as OUTDATED pending a new owner golden batch;
  43-case deterministic scores against the old batch are stale until that
  refresh and cannot establish V9 answer correctness.

### V9 Model Max Brand Extension (2026-09-16)

- The owner-supplied bilingual `model-max-brand-intro-20260916.md` is the
  sole authority for Model Max brand facts. Vendor it verbatim at
  `tests/chat_eval/fixtures/model_max_brand_intro_20260916.md`, pinned to
  SHA-256
  `804c810f8167941da76927d5962c19ee1b7fb7634a8b69b1b6a660c705d53bd4`.
  The approved Chinese and English introductions are:

  > 面向 AI coding agent 的统一网关。单一入口与统一额度，后面接多个上游供应商。原生支持 Codex 协议，工具调用与多轮上下文完整透传。第一版覆盖 OpenAI 系列模型与 Astra。

  > A unified AI gateway built for coding agents. One endpoint and quota across multiple upstream providers. Native Codex protocol support with tool calls and multi-turn context intact. V1 covers OpenAI models and Astra.

- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R21`: extend the not-yet-shipped source
  set `marketplace-qna-bilingual-2026-09-16-v9` with document pair 18,
  `zh-CN/18_Model-Max-品牌事实.md` and `en/18_Model-Max-Brand-Facts.md`.
  These documents carry Model Max brand identity only. Their five Q&As per
  language cover the complete introduction, V1 OpenAI models and Astra,
  native Codex protocol with intact tool calls and multi-turn context, one
  endpoint and quota across multiple upstream providers, and current-page
  routing for Agent-specific facts. The current Model Max Consumer Agent
  identity (#212) is task context, not a fixed corpus identifier.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R22`: every document-18 question,
  Golden Query, and representative chat case uses Model Max branding to
  separate these facts from PixVerse and generic Consumer content. The
  identity answer preserves the complete approved introduction verbatim;
  subsequent answers retain Model Max vocabulary. Do not
  infer pricing, quota numbers, code-redemption details, account requirements,
  partnership boundaries, availability, or any other unsupported capability.
  Agent-specific thresholds, benefits, and fees are resolved only through the
  current Model Max Agent page or typed context; absent values are not
  invented. Document 18 contains no `Refund` mention; the existing generic
  Consumer policy stays in document 15.
- `SPEC-CONSUMER-GOLDEN-ANSWERS-001-R23`: documents 01-17 remain
  byte-identical to baseline `3d048d6` in this extension. Preserve the old
  Consumer and Rave fixtures, source adapters, regression harness, and
  OUTDATED-case list. Rebuild corpus, Golden Queries, review evidence, and
  chat cases through the existing builder; preserve V9 identifiers, refresh
  hashes and chunk counts, and extend coverage to 36 documents, 346 queries
  and review rows (173 per language), 36 chat cases, and 278 structural
  anchors. A RED-first fixture test must verify the new verbatim source hash.
  This extension authorizes no upload, deployment, commit, or push.

### OUTDATED Consumer Golden Cases Pending New Owner Batch

Question numbers below follow each part's original source order, including the
eight existing intake-blocker gaps. These 17 supplied ideal answers conflict
with the 2026-09-16 directive; each is **OUTDATED** pending a replacement owner
golden batch. This list is documentation only and does not alter case IDs,
emission, scoring rules, or the hash-pinned fixture.

| Source part / question | Supplied question | Superseded claim |
| --- | --- | --- |
| Redemption Q01 | 这个 agent 是做什么的？ | Refund of principal if the user no longer wants the benefits |
| Redemption Q02 | 和直接在【品牌方】官网买有什么区别？ | Funds can be taken back at any time before code redemption |
| Redemption Q07 | 最少要 mint 多少？ | Below-threshold shares may be redeemed for funds |
| Redemption Q15 | 我可以只兑换一部分吗？ | Remaining shares can later be Refunded |
| Redemption Q22 | 怎么把钱拿回来？ | Unredeemed shares return the corresponding principal |
| Redemption Q23 | 所有份额都能赎回吗？ | Unredeemed shares are eligible for Refund |
| Redemption Q26 | 赎回需要等吗？ | Refund application proceeds through Pending and Claimable to collection |
| Redemption Q27 | 赎回有次数限制吗？ | Refund may be requested multiple times without a count limit |
| Redemption Q32 | 如果【品牌方】倒闭了会怎样？ | Brand failure leaves Refund unaffected |
| Redemption Q33 | 份额可以转给别人或在交易所卖掉吗？ | Refund is the current Moss exit route |
| Redemption Q37 | 一共要付哪些费用？ | A Consumer Refund operation charges a Refund fee |
| Redemption Q42 | 显示 Paused by owner 是什么意思？ | Owner pause includes an available Consumer Refund operation |
| Redemption Q43 | 我可以一边拿兑换码一边把钱退回来吗？ | The user can choose between code redemption and Refund |
| Redemption Q45 | 这是保本的吗？ | Principal-protection framing is based on actual Refund value minus fees |
| Redemption Q47 | 出问题找谁？ | Support guidance presents Consumer Refund as an available operation |
| PixVerse Q08 | 这比直接在 PixVerse 官网买便宜吗？ | Refundable principal before code redemption is a purchase advantage |
| PixVerse Q16 | PixVerse 停止支持这个合作了怎么办？ | Partnership termination leaves Refund unaffected |

Redemption Q24 (`赎回之后已经拿到的兑换码还能用吗？`) and Q25
(`赎回要收费吗？`) already have empty answers and remain among the same eight
intake blockers; their Refund premises also require owner refresh, but there
is no supplied ideal answer to rewrite or newly exclude. Redemption Q41
(`为什么按钮是灰的？`) does not name Refund in either the supplied question or
answer, so it is not counted as a conflicting ideal answer. This does not
preserve the separately authored Refund-button Q&A in corpus document 15,
which V9 removes.

### Behavior

R1-R17 retain the existing harness and historical V7/V8 contracts. In
particular, preserved Refund fee dynamic rules and source fact groups are
historical regression behavior; they do not override current Consumer product
truth in R18-R20.

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

Steps 1-14 record the historical V7/V8 implementation. Steps 15-17 record
the initial V9 reversal, which supersedes conflicting refund claims. Steps
18-20 extend the same unshipped V9 seed with approved Model Max brand facts.

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
15. Add meaningful RED corpus/seed regressions for Consumer no-Refund behavior,
    preserved code flow and custody/UI topics, faithful bilingual mirrors, and
    protected non-Consumer content; leave the historical golden fixture and
    regression harness unchanged.
16. Revise bilingual 13-16, rename document 15, replace obsolete Refund-mechanism
    Golden Queries/chat cases with realistic no-Refund coverage, and rebuild
    corpus, Golden Queries, review evidence, and chat cases for V9. Recompute
    production chunks and hashes and refresh the runbook's Reviewed Seed table.
17. Run the fixture builder, Golden Query audit, focused Marketplace/Promptfoo/
    Consumer/Rave tests, full pytest, spec contract, and diff check; attempt the
    spec-registry gate and record any environment blocker. No upload,
    deployment, commit, or push is in scope.
18. Record R21-R23 before corpus implementation, then add meaningful RED
    tests for the exact Model Max source hash, approved-only bilingual brand
    facts, Model Max-scoped query coverage, and expanded V9 counts.
19. Vendor the owner material without edits, add the five-question document-18
    pair and corresponding query/review/chat definitions, and rebuild the
    existing fixture family. Recompute production chunks and hashes; update
    current runbook/review counts without changing documents 01-17.
20. Run the builder, Golden Query audit, focused Marketplace/Promptfoo/source
    tests including the new fixture test, full pytest, spec contract, and diff
    check; attempt the spec-registry gate. Record local-only evidence and
    preserve the user's existing `CLAUDE.md` deletion.

## Closeout Evidence

### Historical V7/V8 Evidence

The evidence below describes the previously implemented seed versions. It does
not validate the Consumer Refund claims superseded on 2026-09-16; in
particular, the reported 43-case deterministic scores are historical and stale
for V9 until the owner refreshes the golden batch.

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

### Historical V9 Reversal Closeout (2026-09-16)

This evidence describes the completed initial V9 reversal before the Model Max
extension. Its 34-document counts and original working-tree baseline are
historical; the committed baseline for the extension is `3d048d6`.

- Approved scope and exact owner wording were recorded before corpus
  implementation. At that closeout, work was uncommitted on
  `feat/consumer-golden-answers` at `7dfa463`; the user's pre-existing
  `CLAUDE.md` deletion was preserved. No commits, pushes, uploads, deployment,
  or provider-backed evaluation ran during that implementation phase.
- V9 contains 34 bilingual documents, 336 Golden Queries and review rows
  (168 per language), 34 representative chat cases, and 268 structural anchors.
  The production chunker emits **305 chunks** at size 400 / overlap 80, down
  from V8's 313. All six manifest hashes verify, and all four generated JSONL
  files exactly match deterministic builder output.
- Document 15 is renamed as specified above; each language now has 11 Q&As
  rather than 18. The builder discovers filenames from the source directory,
  so regenerated `source_path`, `filename`, answer-line evidence, and
  hash-pinned corpus consistently use the new names. Logical document IDs and
  source URIs remain unchanged; question IDs follow the new section order.
- All 26 source files outside documents 13-16 are byte-identical to HEAD,
  including document 03, which contains no Consumer refundability claim.
  Consumer/Rave verbatim fixtures, adapters, and regression scoring remain
  unchanged. The 17 OUTDATED ideal answers and two existing empty-answer
  Refund blockers are documented above; old 43-case scores remain stale.

| Bilingual document | Previous claim | V9 wording / retained boundary |
| --- | --- | --- |
| 13 Consumer Agent / Mint | Unused shares can Refund; shares derive value from Refund | Check all Agent page information before deciding to Mint; benefits, non-investment, and no-APY framing retained |
| 14 Code creation / use | Remaining shares can Refund; consumed shares cannot Refund | Remaining shares continue to be held; consumed shares cannot be restored; all other code-flow steps unchanged |
| 15 Fund safety / UI | Refund eligibility, amount, states, count, grey button, exit, and principal-protection explanations | One exact owner no-Refund answer; custody, shares display, masked activities, page-state pause, and brand-fulfillment boundary retained |
| 16 PixVerse partnership | Unredeemed principal remains in contract when partnership ends | Unredeemed-share assets remain held by the contract; code use depends on PixVerse fulfillment/terms, with no recovery promise |

| Verification | Result |
| --- | --- |
| RED: `pytest -q tests/test_marketplace_qna_eval.py -k v9` | Four intended failures before implementation: duplicated Refund mechanisms and the old chat contract rejecting the owner answer |
| `.venv/bin/python -m tests.rag_eval.marketplace_qna_fixture_builder --write` | Passed; 34 / 336 / 336 / 34 rows |
| `.venv/bin/python -m tests.rag_eval.marketplace_qna_golden_query_audit --output /private/tmp/consumer-v9-golden-query-audit.json` | Passed; no coverage/evidence gaps |
| Focused pytest: `tests/test_marketplace_qna_eval.py tests/test_rag_promptfoo_eval.py tests/test_consumer_golden_source.py tests/test_rave_governance_golden_source.py` | 77 passed, including all four RED-to-GREEN regressions |
| `.venv/bin/python -m pytest -q --junitxml=/private/tmp/consumer-v9-full-pytest.xml` | 762 passed, 1 skipped; no errors or failures |
| `pytest -q tests/test_marketplace_qna_workflow.py` after the final Makefile help-count update | 6 passed; only help text changed, no recipes or deployment behavior |
| `SPEC_CONTRACT_ARTIFACT_DIR=/private/tmp/consumer-v9-spec-contract scripts/check_spec_contract.sh` | Passed; 29 legacy specs and 29 legacy plans |
| `git diff --check` | Passed |
| `HARNESS_ARTIFACT_DIR=/private/tmp/consumer-v9-spec-registry scripts/check_spec_registry.sh` | Attempted; blocked fetching pinned harnessctl v0.3.0 because sandbox DNS could not resolve `proxy.golang.org` |
| Independent diff review | Source semantics, 17-case conflict list, fixture preservation, and hashes verified; stale Makefile help counts corrected to 336 |

Changed-file inventory (excluding the user's untouched `CLAUDE.md` deletion):

- `tests/rag_eval/marketplace_qna_sources/zh-CN/13_Consumer-Agent-与-Mint.md`
  and `en/13_Consumer-Agent-and-Mint.md`.
- `tests/rag_eval/marketplace_qna_sources/zh-CN/14_兑换码生成与使用.md`
  and `en/14_Redemption-Code-Creation-and-Use.md`.
- `tests/rag_eval/marketplace_qna_sources/zh-CN/15_Refund-资金安全与界面状态.md`
  → `15_资金安全与界面状态.md`; English
  `en/15_Refund-Fund-Safety-and-UI-States.md`
  → `15_Fund-Safety-and-UI-States.md`.
- `tests/rag_eval/marketplace_qna_sources/zh-CN/16_PixVerse-品牌与合作边界.md`
  and `en/16_PixVerse-Brand-and-Partnership-Boundaries.md`.
- Under `tests/rag_eval/`: `marketplace_qna_fixture_builder.py`,
  `marketplace_qna_case_definitions.jsonl`, `marketplace_qna_corpus.jsonl`,
  `marketplace_qna_golden_queries.jsonl`,
  `marketplace_qna_golden_query_review.jsonl`, `marketplace_qna_chat_cases.jsonl`,
  `marketplace_qna_coverage_contract.json`,
  `marketplace_qna_acceptance_evidence_contract.json`,
  `marketplace_qna_golden_query_audit.py`,
  `marketplace_qna_rag_seed_manifest.json`.
- `tests/test_marketplace_qna_eval.py`, `tests/test_marketplace_qna_workflow.py`,
  `docs/MARKETPLACE_QNA_RAG_INGESTION_RUNBOOK.md`,
  `docs/MARKETPLACE_QNA_GOLDEN_QUERIES_REVIEW.md`, `Makefile` (help counts only),
  and this specification.

### V9 Model Max Extension Closeout (2026-09-16)

- R21-R23 and the exact bilingual source/hash were recorded before corpus
  implementation. The extension uses baseline `3d048d6` on
  `feat/consumer-golden-answers` and remains uncommitted; the user's existing
  `CLAUDE.md` deletion is preserved. No upload, deployment, commit, push, live
  retrieval, or provider-backed acceptance ran.
- Final V9 totals: **36 documents, 346 Golden Queries, 346 review rows,
  36 chat cases, 278 structural anchors, 310 chunks**. Each language has
  18 documents and 173 queries. Doc 18 adds 2 Chinese and 3 English chunks
  under production size 400 / overlap 80; the preceding 305 chunks remain
  unchanged. Source set, manifest ID, and knowledge-base name stay V9.
- Owner fixture bytes match the supplied file and pinned SHA exactly. All
  34 source files for documents 01-17 are byte-identical to `3d048d6`. All
  existing generated rows also remain identical: 34 corpus rows, 336 queries,
  336 review rows, and 34 chat cases. The four generated JSONL files exactly
  match builder output, and all six manifest fixture hashes verify.
- All five new questions in each language and their retrieval/chat queries
  explicitly name Model Max. The first answer preserves the complete owner
  paragraph verbatim; the remaining brand answers restate only approved facts.
  The final question routes Agent-specific values to the current page or typed
  context. Doc 18 contains no Refund reference or alternative exit mechanism.

| Doc 18 question (faithful English mirror included) | Answer boundary |
| --- | --- |
| Model Max 是什么，主要面向谁？ | Full verbatim bilingual owner introduction |
| Model Max 第一版覆盖哪些模型？ | OpenAI models and Astra |
| Model Max 支持什么协议，怎样处理工具调用与多轮上下文？ | Native Codex protocol; tool calls and multi-turn context intact |
| Model Max 的单一入口与统一额度是什么意思？ | One endpoint and quota across multiple upstream providers |
| Model Max Agent 的兑换门槛、权益内容和费用要在哪里确认？ | Current Model Max Agent page or typed context; never inferred from the brand introduction |

| Verification | Result |
| --- | --- |
| RED: `.venv/bin/python -m pytest -q tests/test_model_max_brand_source.py` | Five expected failures before implementation: missing owner fixture, bilingual document 18, and bilingual chat cases |
| `.venv/bin/python -m tests.rag_eval.marketplace_qna_fixture_builder --write` | Passed; 36 / 346 / 346 / 36 rows |
| `.venv/bin/python -m tests.rag_eval.marketplace_qna_golden_query_audit --output /private/tmp/model-max-v9-golden-query-audit.json` | Passed; no coverage or evidence gaps |
| Focused pytest: Marketplace QnA eval/workflow, Promptfoo, Consumer source, Rave source, and Model Max source suites | 88 passed; five new regressions GREEN |
| `.venv/bin/python -m pytest -q --junitxml=/private/tmp/model-max-v9-full-pytest.xml` | 767 passed, 1 skipped; no errors or failures |
| `SPEC_CONTRACT_ARTIFACT_DIR=/private/tmp/model-max-v9-spec-contract scripts/check_spec_contract.sh` | Passed; 29 legacy specs and 29 legacy plans |
| `git diff --check` | Passed |
| `HARNESS_ARTIFACT_DIR=/private/tmp/model-max-v9-spec-registry scripts/check_spec_registry.sh` | Attempted; pinned harnessctl fetch blocked because sandbox DNS could not resolve `proxy.golang.org` |
| Independent read-only review | No actionable findings; approved-fact scope, prior source/case-row preservation, hashes, deterministic artifacts, and counts verified |

Changed-file inventory for this extension (excluding the untouched user
`CLAUDE.md` deletion):

- New: `tests/chat_eval/fixtures/model_max_brand_intro_20260916.md`,
  `tests/test_model_max_brand_source.py`,
  `tests/rag_eval/marketplace_qna_sources/zh-CN/18_Model-Max-品牌事实.md`,
  `tests/rag_eval/marketplace_qna_sources/en/18_Model-Max-Brand-Facts.md`.
- Under `tests/rag_eval/`: `marketplace_qna_fixture_builder.py`,
  `marketplace_qna_case_definitions.jsonl`, `marketplace_qna_corpus.jsonl`,
  `marketplace_qna_golden_queries.jsonl`,
  `marketplace_qna_golden_query_review.jsonl`, `marketplace_qna_chat_cases.jsonl`,
  `marketplace_qna_coverage_contract.json`,
  `marketplace_qna_acceptance_evidence_contract.json`,
  `marketplace_qna_golden_query_audit.py`,
  `marketplace_qna_rag_seed_manifest.json`.
- `tests/test_marketplace_qna_eval.py`, `tests/test_marketplace_qna_workflow.py`,
  `docs/MARKETPLACE_QNA_RAG_INGESTION_RUNBOOK.md`,
  `docs/MARKETPLACE_QNA_GOLDEN_QUERIES_REVIEW.md`, `Makefile` (help counts only),
  and this specification.
