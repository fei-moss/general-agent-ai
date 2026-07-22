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
  "applicable_agent_types": ["hyperliquid"],
  "source_question_id": "Q9",
  "dynamic_fact_variables": ["redemption_policy"],
  "dynamic_fact_rules": ["current_agent_redemption_policy"],
  "tags": ["mint", "marketplace"]
}
```

`ideal_answer` 完整保留，语义评审不要求逐字复现。`required_fact_groups` 只放必须命中的关键事实；每个内层数组是可接受表述的 OR 组。产品负责人确认通过 `--approved-by` 和 `--source-version` 固化到正式案例中。真实密钥和真实钱包地址会被拒绝。

`applicable_agent_types` 是可选的小写 Agent 类型列表。运营文档只覆盖 Hyperliquid 时，案例应标记 `hyperliquid`；在其他类型 Agent 上运行会记录为 `not_applicable`，不会误报产品缺陷。没有该字段的旧案例保持原行为。

`source_question_id` 保留产品文档内的原始题号；`dynamic_fact_variables` 保留样例中必须由当前 Agent 配置或链上数据填充的变量名。两者都是审计元数据，不会把变量值写进 Prompt。业务范围、语言与风险分别由 `area`、`locale`、`risk_level` 固化。

`dynamic_fact_rules` 用于会随当前 Agent 配置变化的事实。目前支持：

- `current_agent_redemption_policy`：锁定期以及 request / claim 流程。
- `current_agent_fee_schedule`：当前可见费用名称与费率。
- Ballot 项目与收益：`project_name`、`project_token`、`fixed_apy`、
  `accrual_display_location`、`reward_source_summary`、`yield_denomination`、
  `airdrop_token`。
- Ballot 治理与退出：`proposal_creation_rule`、`proposal_threshold`、
  `proposal_display_location`、`voting_power_rule`、`snapshot_timing_rule`、
  `vote_change_rule`、`vote_cost_note`、`governance_rewards_rule`、
  `gov_reward_detail`、`execution_rule`、`early_redeem_rule`、
  `redeem_during_vote_rule`、`concentration_note`。

Ballot 动态规则若未出现在当前 `ai-context`，目标真值会显式标记
`not_provided`；这要求回答保留稳定机制说明，同时不得用示例值填空。

包含动态规则或 Agent 类型约束的批次，报告阶段必须提供一个不含地址、钱包或凭据的当前 Agent 真值快照。例如：

```json
{
  "agent_type": "hyperliquid",
  "dynamic_facts": {
    "current_agent_redemption_policy": {
      "required_fact_groups": [
        ["10000 seconds", "10000 秒", "2h 46m 40s", "2 小时 46 分 40 秒"],
        ["claim", "领取"],
        ["settlement", "结算"]
      ],
      "forbidden_claims": ["no lock-up", "没有锁定期"]
    },
    "current_agent_fee_schedule": {
      "required_fact_groups": [
        ["management fee", "management_fee", "管理费"],
        ["100 bps", "100 basis points", "1%"]
      ],
      "forbidden_claims": []
    }
  }
}
```

这里的数值只是目标 Agent 当次配置快照，不写入 Prompt，也不回填覆盖产品负责人原始答案。目标 Agent 改变或配置改变时，重新生成快照。不要根据页面标签手写费用类型；例如页面可能显示 `Mint fee`，但 Marketplace 类型化合同返回 `management_fee` 时，评测和 Chat 都必须使用后者。

如果产品答案中的静态句子与当前 Agent 动态配置冲突，标准化阶段要保留原始 `ideal_answer` 作为审批证据，但从静态 `required_fact_groups` 中移除冲突项，并用对应 `dynamic_fact_rules` 验收当前真值。例如，产品样例写“随时退出”而目标 Agent 有赎回锁定时，回答和硬验收都必须以当前锁定配置为准。

从 Marketplace `ai-context` 原始 JSON 自动生成脱敏真值：

```bash
.venv/bin/python -m tests.chat_eval.approved_case_workflow target-truth \
  --context /path/to/current-agent-ai-context.json \
  --output /path/to/current-agent-target-truth.json
```

生成器只保留 Agent Type、动态规则、机器值的可接受表达以及与当前配置冲突的禁止说法；Agent 地址、钱包、用户上下文、报告和其他原始响应字段不会进入输出。

## 标准执行

固定顺序是：结构化 → 冻结契约 → 一次 baseline → 批量归因 → 本地修复 → 一次完整回归 → 单体 closeout。不得从逐题 live 结果直接追加问题字符串、Agent ID、示例答案或模型措辞规则。

先固化正式 cases，再冻结适用类型、稳定事实和当前动态真值：

```bash
.venv/bin/python -m tests.chat_eval.approved_case_workflow ingest \
  --input /path/to/normalized-input.jsonl \
  --output /path/to/approved-cases.jsonl \
  --approved-by marketplace-product-owner \
  --source-version ops-golden-v1

.venv/bin/python -m tests.chat_eval.approved_case_workflow preflight \
  --cases /path/to/approved-cases.jsonl \
  --target-truth /path/to/current-agent-target-truth.json \
  --output /path/to/approved-golden-preflight.json
```

`preflight` 输出事实矩阵与 case/target-truth 哈希。适用类型、动态规则或当前真值未冻结时状态为 `blocked`，approved case live runner 会拒绝启动。

只运行一次完整 baseline：

```bash
.venv/bin/python -m tests.chat_eval.live_runner \
  --case-file /path/to/approved-cases.jsonl \
  --preflight /path/to/approved-golden-preflight.json \
  --target-truth /path/to/current-agent-target-truth.json \
  --base-url "$CHAT_EVAL_BASE_URL" \
  --marketplace-user-id "$CHAT_EVAL_MARKETPLACE_USER_ID" \
  --marketplace-wallet "$CHAT_EVAL_MARKETPLACE_WALLET" \
  --output /path/to/approved-golden-live.json
```

生成差距、语义评审包和批量修复清单：

```bash
.venv/bin/python -m tests.chat_eval.approved_case_workflow report \
  --cases /path/to/approved-cases.jsonl \
  --baseline /path/to/approved-golden-live.json \
  --target-truth /path/to/current-agent-target-truth.json \
  --output /path/to/approved-golden-report.json \
  --strict-hard
```

`report.attribution_summary` 与 `repair_batches` 按 Prompt/答案组织、RAG、工具、数据、Guardrail、运行时、产品行为或评估器聚合失败。语义缺失和普通事实遗漏的 `runtime_retry_guard_allowed` 恒为 `false`；只有高风险禁止断言才允许进入运行时 guard。

同一失败批次再次出现时，先生成迭代决策：

```bash
.venv/bin/python -m tests.chat_eval.approved_case_workflow decision \
  --report /path/to/current-report.json \
  --previous-report /path/to/previous-report.json \
  --output /path/to/iteration-decision.json
```

连续两轮签名相同会返回 `stop_and_redesign` 并以非零退出，禁止继续补措辞或重复部署；应回到对应根因批次做通用修复。

Approved case 使用 `--case-id` 或 tag 做 targeted rerun 时必须同时传入最新的 `--iteration-decision`；预算已耗尽或尚未完成语义评审时，live runner 会拒绝请求。

最终在最新提交上重新运行不带筛选参数的完整 suite，并生成单体 closeout：

```bash
.venv/bin/python -m tests.chat_eval.approved_case_workflow closeout \
  --cases /path/to/approved-cases.jsonl \
  --preflight /path/to/approved-golden-preflight.json \
  --baseline /path/to/final-full-suite.json \
  --report /path/to/final-report.json \
  --output /path/to/final-closeout.json
```

`closeout` 要求所有适用案例来自同一个 `full_suite`，且 hard failure、semantic gap、pending review、release blocker 和 completion blocker 都为零。把 targeted retry 结果拼进完整报告会因 suite ID 不一致而失败。

产物路径由执行者显式指定。覆盖摘要只显示当前 `area`、风险等级和标签数量，不产生业务完整度 blocker。后续批次使用 `--existing` 写入新的版本化输出；相同 ID 的内容冲突会停止，不会覆盖已确认事实。

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
  --target-truth /path/to/current-agent-target-truth.json \
  --semantic-reviews /path/to/semantic-reviews.jsonl \
  --output /path/to/approved-golden-report.json \
  --strict-hard
```

关键事实缺失、禁止内容、请求失败属于硬 blocker。LLM 语义评审当前是观察项；低风险 `gap` 进入优化清单，高风险或关键案例的 `gap` 同时进入完成 blocker。

完成语义评审后重新生成 `report`，但在本地测试和确定性 evaluator 未通过前不得启动下一次完整 live run。工具应该调用却没有调用归因到 `tool_behavior`；当前真值缺失归因到 `data_behavior`；工具已返回但答案遗漏归因到 Prompt/答案组织；评估规则本身错误归因到 `evaluator_behavior`。

当已确认 Golden Case 补充的是稳定平台机制，而现有知识库没有覆盖时，应把事实合并到规范的 Marketplace QnA 来源，生成新的版本化 corpus 和知识库，验收后切换 `RAG_DEFAULT_KNOWLEDGE_BASE_ID`；旧知识库保留用于回滚。不要把新事实追加到旧知识库，也不要把动态 Agent 数值写进固定知识文档。
