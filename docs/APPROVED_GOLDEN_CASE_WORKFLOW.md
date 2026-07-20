# Approved Golden Case Workflow

这条工作流接收运营提供、且产品负责人已确认的优质问答，用它们建立增量问答优化回归。它不要求穷举完整业务覆盖，也不会自动修改 Prompt、运行时代码或生产配置。

## 输入契约

运营输入可以是 Markdown、表格、CSV 或 JSON。执行前由工程 Agent 标准化为 JSON/JSONL；每条正式案例至少包含：

```json
{
  "id": "marketplace_mint_meaning_zh",
  "question": "Mint 一个 Agent 的份额是什么意思？",
  "ideal_answer": "Mint 会获得 Agent 的链上份额，份额价值会随 Agent 管理资产变化。",
  "area": "marketplace",
  "required_fact_groups": [
    ["链上份额", "Agent 份额"],
    ["份额价值", "份额价格"]
  ],
  "forbidden_claims": ["固定收益"],
  "requires_rag": true,
  "risk_level": "high",
  "tags": ["mint", "marketplace"]
}
```

`ideal_answer` 完整保留，语义评审不要求逐字复现。`required_fact_groups` 只放必须命中的关键事实；每个内层数组是可接受表述的 OR 组。产品负责人确认通过 `--approved-by` 和 `--source-version` 固化到正式案例中。真实密钥和真实钱包地址会被拒绝。

## 标准执行

先将本批输入固化成正式 cases：

```bash
.venv/bin/python -m tests.chat_eval.approved_case_workflow ingest \
  --input /path/to/normalized-input.jsonl \
  --output /path/to/approved-cases.jsonl \
  --approved-by marketplace-product-owner \
  --source-version ops-golden-v1
```

再对目标 API 生成 baseline：

```bash
.venv/bin/python -m tests.chat_eval.live_runner \
  --case-file /path/to/approved-cases.jsonl \
  --base-url "$CHAT_EVAL_BASE_URL" \
  --marketplace-user-id "$CHAT_EVAL_MARKETPLACE_USER_ID" \
  --marketplace-wallet "$CHAT_EVAL_MARKETPLACE_WALLET" \
  --output /path/to/approved-golden-live.json
```

最后生成差距和语义评审包：

```bash
.venv/bin/python -m tests.chat_eval.approved_case_workflow report \
  --cases /path/to/approved-cases.jsonl \
  --baseline /path/to/approved-golden-live.json \
  --output /path/to/approved-golden-report.json \
  --strict-hard
```

三个阶段分别完成：

1. `ingest`：校验确认信息，标准化并增量合并正式 cases。
2. `live_runner --case-file`：使用正式 cases 回放目标 API。
3. `report`：检查关键事实和禁止内容，输出归因建议及待语义评审包。

产物路径由执行者显式指定。覆盖摘要只显示当前 `area`、风险等级和标签数量，不产生业务完整度 blocker。

后续批次通过 `--existing /path/to/current-approved-cases.jsonl` 读取现有正式集，并写入一个新的版本化输出文件。完全相同的案例会被忽略；相同 `id` 但业务内容不同会停止并要求人工解决，不会静默覆盖已确认事实。

## 语义评审与收敛

第一次报告的 `semantic_review_packet` 可交给 Codex 或其他评审模型。评审结果使用 JSONL，每条包含：

```json
{
  "case_id": "marketplace_mint_meaning_zh",
  "verdict": "pass",
  "reason": "措辞不同但核心业务语义完整。",
  "gaps": [],
  "attribution": "none",
  "dimension_scores": {"correctness": 2, "completeness": 2}
}
```

`verdict` 可以是 `pass`、`gap` 或 `accepted_variance`。普通措辞差异可以记录为 `accepted_variance`，避免为了分数过度拟合标准答案。将评审文件传回报告：

```bash
.venv/bin/python -m tests.chat_eval.approved_case_workflow report \
  --cases /path/to/approved-cases.jsonl \
  --baseline /path/to/approved-golden-live.json \
  --semantic-reviews /path/to/semantic-reviews.jsonl \
  --output /path/to/approved-golden-report.json \
  --strict-hard
```

关键事实缺失、禁止内容、请求失败属于硬 blocker。LLM 语义评审当前是观察项；低风险 `gap` 进入优化清单，高风险或关键案例的 `gap` 同时进入完成 blocker。

报告只建议归因到 Prompt/回答组织、RAG/检索、工具/数据、Guardrail/策略、运行时或产品行为。涉及 Prompt 核心语义、运行时、工具/API 和安全边界时，先确认修改清单，再实施和重新回放。
