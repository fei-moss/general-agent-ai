"""Built-in Agent Protocol FAQ V1 retrieval fixture."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


_DOCUMENT_ID = "agent_protocol_faq_v1"
_KNOWLEDGE_BASE_ID = "builtin:agent_protocol_faq_v1"
_SOURCE_URI = "https://merlinchain.sg.larksuite.com/wiki/AeeywtmIniGvqxkTPF7l1ZWJgdf"
_ASCII_TOKEN_RE = re.compile(r"[a-z0-9_]+")


@dataclass(frozen=True)
class PlatformFAQEntry:
    """One PM-approved FAQ answer packaged as a retrievable chunk."""

    id: str
    section: str
    question: str
    answer: str
    keywords: tuple[str, ...]
    boundary: bool = False


_FAQ_ENTRIES: tuple[PlatformFAQEntry, ...] = (
    PlatformFAQEntry(
        id="mint_redeem_definition",
        section="Mint / Redeem",
        question="Mint 和 Redeem 分别是什么?",
        answer=(
            "Mint 是铸造 Agent 份额, Redeem 是赎回 Agent 份额。FAQ V1 的口径是:"
            " 策略收益通过 exchangeRate 上升体现在份额价值里, 用户 Redeem 时按当前"
            " exchangeRate 结算, 没有独立的 Claim Yield 操作。"
        ),
        keywords=("mint", "redeem", "铸造", "赎回", "份额", "claim yield", "exchangerate"),
    ),
    PlatformFAQEntry(
        id="mint_redeem_approval_flow",
        section="Mint / Redeem",
        question="为什么 Mint / Redeem 要点两次?",
        answer=(
            "Mint / Redeem 采用申请和最终执行两段流程: 用户先提交申请并签名, 按钮进入"
            " Awaiting Approval; 审批通过后收到通知, 再次点击 Mint 或 Redeem 进行最终"
            " 交易签名和广播。Awaiting Approval 状态刷新页面后仍会保留; 审批拒绝会恢复按钮。"
        ),
        keywords=("两次", "approval", "awaiting approval", "申请", "审批", "签名", "广播"),
    ),
    PlatformFAQEntry(
        id="redeem_disabled_no_shares",
        section="Mint / Redeem",
        question="没有份额时为什么不能 Redeem?",
        answer="如果用户没有持有任何 shares, Redeem Tab 会置灰, 页面提示 You don't hold any shares。",
        keywords=("没有份额", "no shares", "don't hold any shares", "redeem tab", "置灰"),
    ),
    PlatformFAQEntry(
        id="redeem_disabled_insufficient_balance",
        section="Mint / Redeem",
        question="Redeem 金额超过余额时怎么提示?",
        answer="当 Redeem 数量超过用户持有份额时, FAQ V1 要求提示 Insufficient balance。",
        keywords=("insufficient balance", "余额不足", "超过余额", "redeem 数量"),
    ),
    PlatformFAQEntry(
        id="mint_sold_out_supply_cap",
        section="Mint / Redeem",
        question="Supply Cap 到达上限后还能 Mint 吗?",
        answer="当 Available 为 0 或 Supply Cap reached 时, Mint 按钮置灰, 页面提示 Sold out。",
        keywords=("supply cap", "available", "sold out", "mint 按钮", "上限"),
    ),
    PlatformFAQEntry(
        id="wallet_connect_required",
        section="Mint / Redeem",
        question="未连接钱包点击 Mint / Redeem 会怎样?",
        answer="未连接钱包时点击 Mint 或 Redeem, 应先触发 Connect Wallet。",
        keywords=("connect wallet", "未连接钱包", "钱包连接", "metamask", "walletconnect"),
    ),
    PlatformFAQEntry(
        id="supply_cap_total_supply",
        section="Mint / Redeem",
        question="Supply Cap 和 totalSupply 有什么区别?",
        answer="Supply Cap 是发行上限, totalSupply 是当前已发行份额数量。",
        keywords=("supply cap", "totalsupply", "发行上限", "已发行"),
    ),
    PlatformFAQEntry(
        id="accept_token",
        section="Mint / Redeem",
        question="Mint 支付用什么 Token?",
        answer="Mint 支付 Token 由合约的 Accept Token 定义, 不是固定 ETH。",
        keywords=("accept token", "支付 token", "不是固定 eth", "mint token"),
    ),
    PlatformFAQEntry(
        id="multichain_independent_entries",
        section="Multi-chain",
        question="同一个 Agent 策略部署到多条链时如何展示?",
        answer=(
            "同一策略可以部署到多条链, 但每条链是独立入口。Marketplace 不做跨链聚合,"
            " Price、Holders、AUM 等链上数据按链独立展示, 名称可带 ETH、BASE 等链标签。"
        ),
        keywords=("multi-chain", "多链", "跨链", "独立入口", "不聚合", "holders", "aum"),
    ),
    PlatformFAQEntry(
        id="hyperliquid_template_chain",
        section="Multi-chain",
        question="Hyperliquid 模板支持哪些链?",
        answer="FAQ V1 只写明 Hyperliquid 模板支持 HyperEVM, 不作为多链模板处理。",
        keywords=("hyperliquid", "hyperevm", "模板", "多链模板"),
    ),
    PlatformFAQEntry(
        id="portfolio_chain_aggregation",
        section="Portfolio / Profile",
        question="Portfolio 是否聚合同一个钱包的多条链?",
        answer=(
            "Portfolio 会按同类地址自动聚合已支持链, 例如同一 EVM 地址在 ETH、BASE、MERL"
            " 上的数据。非 EVM 链暂不支持自动聚合。"
        ),
        keywords=("portfolio", "聚合", "evm", "eth", "base", "merl", "非 evm"),
    ),
    PlatformFAQEntry(
        id="price_unavailable_usd",
        section="Asset Value / USD",
        question="资产价格不可用时怎么展示?",
        answer=(
            "资产统一以 USD 展示。价格不可用时, 该资产 USD 价值按 0 处理, 字段展示"
            " --, tooltip 为 Price unavailable; Portfolio Value 和 PnL 会排除该资产。"
        ),
        keywords=("price unavailable", "价格不可用", "usd", "portfolio value", "pnl", "tooltip"),
    ),
    PlatformFAQEntry(
        id="top_holders_source",
        section="Top Holders",
        question="Top Holders 的数据来源是什么?",
        answer="Top Holders 来源于链上 balanceOf 或 SharesMinted / SharesRedeemed 事件快照。",
        keywords=("top holders", "balanceof", "sharesminted", "sharesredeemed", "事件快照"),
    ),
    PlatformFAQEntry(
        id="top_holders_empty",
        section="Top Holders",
        question="totalSupply 为 0 时 Top Holders 怎么展示?",
        answer="totalSupply 为 0 时, Top Holders 展示 No holders yet。",
        keywords=("no holders yet", "totalsupply", "0", "top holders 空"),
    ),
    PlatformFAQEntry(
        id="dex_pair_visibility",
        section="Trade on DEX",
        question="Trade on DEX 模块什么时候展示?",
        answer="只有 Agent share 存在对应 DEX pair 时才展示 Trade on DEX; 否则隐藏模块, 不展示占位。",
        keywords=("trade on dex", "dex pair", "隐藏", "占位"),
    ),
    PlatformFAQEntry(
        id="live_activity_marketplace_records",
        section="Live Activity",
        question="Live Activity 显示什么?",
        answer=(
            "Live Activity 显示其他用户的 Mint、Redeem、Transfer 记录, 字段包括操作标签"
            " MINT/REDEEM/TRANSFER、钱包地址前 6 后 4 位、share amount、amount、相对时间,"
            " 并按时间倒序展示。它不同于 Agent Live Activities。"
        ),
        keywords=("live activity", "mint", "transfer", "钱包", "share amount", "相对时间"),
    ),
    PlatformFAQEntry(
        id="marketplace_list_rules",
        section="Marketplace List",
        question="Marketplace 列表怎么排序和分页?",
        answer=(
            "Marketplace 默认展示 All Agents。New Tab 展示 3 天内创建的 Agents, 按创建时间倒序,"
            " 每 24 小时刷新范围。列表每次加载 20 条, 使用无限滚动, 不提供分页器。同一策略"
            " 在不同链上不合并。"
        ),
        keywords=("marketplace", "new tab", "3 天", "20 条", "无限滚动", "不合并"),
    ),
    PlatformFAQEntry(
        id="create_agent_paths",
        section="Create Agent",
        question="Create Agent 有哪些路径?",
        answer=(
            "Create Agent 有 Template Setup 和 Developer Deploy 两条路径。FAQ V1 明确当前主路径"
            " 是 Template Setup; Developer Deploy 还未开发开放。"
        ),
        keywords=("create agent", "template setup", "developer deploy", "创建 agent"),
    ),
    PlatformFAQEntry(
        id="create_agent_steps",
        section="Create Agent",
        question="Template Setup 创建 Agent 的步骤是什么?",
        answer=(
            "Template Setup 流程为 Choose Template、Basic Info、Contract & Agent Setup、Deploy。"
            " Continue 和 Back 会保留字段; Step 3 选择链后加载链相关参数并展示预览、估算 gas、"
            " Protocol fee 和 Total to deploy; Deploy 后等待链确认并跳转详情页。"
        ),
        keywords=("choose template", "basic info", "contract", "deploy", "protocol fee", "estimated gas"),
    ),
    PlatformFAQEntry(
        id="ask_this_agent_positioning",
        section="Ask this Agent",
        question="Ask this Agent 是协议的一部分吗?",
        answer=(
            "Ask this Agent 不是协议的一部分, 是中心化平台基于当前 Agent 链上数据和创建者策略"
            "描述提供的问答服务。未连接钱包也可以使用。"
        ),
        keywords=("ask this agent", "不是协议", "中心化", "未连接钱包", "问答服务"),
    ),
    PlatformFAQEntry(
        id="ask_this_agent_scope",
        section="Ask this Agent",
        question="Ask this Agent 能回答哪些问题?",
        answer=(
            "Ask this Agent 的回答范围是当前 Agent 的链上数据和创建者策略描述。预设问题 chip"
            " 等同于发送那条问题。超出协议或当前 Agent 范围的问题不应自由发挥。"
        ),
        keywords=("回答范围", "策略描述", "预设问题", "chip", "当前 agent"),
    ),
    PlatformFAQEntry(
        id="agent_live_activities_reports",
        section="Agent Live Activities",
        question="Agent Live Activities 展示什么?",
        answer=(
            "Agent Live Activities 展示 Agent 上报的推理、决策、操作过程, 数据直接来自 Agent"
            " reports。内容为自然语言段落, 非结构化完整展示; 顶部时间 tabs 默认最新记录,"
            " 点击切换时展示 skeleton, 并支持向右无限滚动加载更早记录。"
        ),
        keywords=("agent live activities", "reports", "推理", "决策", "操作过程", "skeleton"),
    ),
    PlatformFAQEntry(
        id="portfolio_profile_tabs",
        section="Portfolio / Profile",
        question="Portfolio / Profile 有哪些 Tab?",
        answer="Portfolio / Profile 包含 Holdings、Created、Earnings 三个 Tab, 默认 Holdings。",
        keywords=("holdings", "created", "earnings", "profile", "tab"),
    ),
    PlatformFAQEntry(
        id="portfolio_overview_metrics",
        section="Portfolio / Profile",
        question="Portfolio Overview 指标怎么解释?",
        answer=(
            "Overview 指标包括 Portfolio Value、Total PnL、Monthly PnL, 都以 USD 展示。"
            "Portfolio Value 是跨支持链聚合的 USD 总额, 副标题为 across N chains; 交易次数"
            " 也按聚合链统计。"
        ),
        keywords=("portfolio value", "total pnl", "monthly pnl", "across n chains", "交易次数"),
    ),
    PlatformFAQEntry(
        id="portfolio_earnings_visibility",
        section="Portfolio / Profile",
        question="Earnings Tab 谁能看到?",
        answer="Earnings Tab 只对本人可见, 交易历史按时间倒序展示并支持无限滚动。",
        keywords=("earnings", "本人可见", "交易历史", "events", "无限滚动"),
    ),
    PlatformFAQEntry(
        id="non_functional_support",
        section="Non-functional",
        question="Agent Protocol 市场支持哪些浏览器和钱包?",
        answer=(
            "FAQ V1 的非功能口径是 PC Web 支持 Chrome、Firefox、Safari, 移动端响应式"
            " 最小宽度 375px; 钱包支持 MetaMask 和 WalletConnect, Coinbase 后续支持。"
        ),
        keywords=("chrome", "firefox", "safari", "375", "metamask", "walletconnect", "coinbase"),
    ),
    PlatformFAQEntry(
        id="api_degraded_behavior",
        section="Non-functional",
        question="后端接口超时时页面应该怎样处理?",
        answer="后端超时时不应白屏, 应保留上一次渲染数据并进入降级策略。",
        keywords=("超时", "白屏", "降级", "保留上一次", "timeout"),
    ),
    PlatformFAQEntry(
        id="navigation",
        section="Navigation",
        question="顶部导航包含哪些入口?",
        answer="顶部导航固定展示 Marketplace、Create Agent、Portfolio、Docs; 当前页面导航加粗高亮。",
        keywords=("navigation", "marketplace", "create agent", "portfolio", "docs", "导航"),
    ),
    PlatformFAQEntry(
        id="private_key_custody",
        section="Safety / Compliance",
        question="平台会托管用户私钥吗?",
        answer="平台不会托管用户私钥; 所有资产操作都需要用户在本地钱包签名。",
        keywords=("私钥", "托管", "private key", "本地钱包签名", "资产操作"),
    ),
    PlatformFAQEntry(
        id="chain_data_integrity",
        section="Safety / Compliance",
        question="链上数据和记录可以被平台随意修改吗?",
        answer=(
            "FAQ V1 的口径是链上数据不可篡改, PnL、交易记录、Activity 直接来自节点或"
            " Agent reports。回答时应说明数据来源, 但不能把它扩展为收益或安全承诺。"
        ),
        keywords=("链上数据", "不可篡改", "节点", "activity", "交易记录", "reports"),
    ),
    PlatformFAQEntry(
        id="risk_disclaimer",
        section="Safety / Compliance",
        question="AI Agent 投资风险怎么提示?",
        answer="风险提示应展示: AI agents involve financial risk. Past performance does not guarantee future results.",
        keywords=("风险提示", "financial risk", "past performance", "future results", "disclaimer"),
    ),
    PlatformFAQEntry(
        id="gap_profit_share",
        section="FAQ Gap",
        question="Profit Share 什么时候收取?",
        answer=(
            "FAQ V1 未覆盖 Profit Share 的收取时间或结算公式。回答时应明确当前 FAQ 未定义,"
            " 不要编造按 Redeem、周期或其他时点收取的规则。"
        ),
        keywords=("profit share", "收益分成", "什么时候收取", "结算公式", "收取时间"),
        boundary=True,
    ),
    PlatformFAQEntry(
        id="gap_management_fee",
        section="FAQ Gap",
        question="Management Fee 怎么计算?",
        answer=(
            "FAQ V1 未覆盖 Management Fee 的具体计算公式。可以说明这是需要 PM 或平台文档"
            " 补充的机制口径, 但不能替用户计算最终收益。"
        ),
        keywords=("management fee", "管理费", "计算公式", "怎么计算", "最终收益"),
        boundary=True,
    ),
    PlatformFAQEntry(
        id="gap_paused_redeem",
        section="FAQ Gap",
        question="Paused 状态下为什么不能 Redeem?",
        answer=(
            "FAQ V1 未覆盖 Paused 状态下 Redeem 受限的具体原因。FAQ V1 已覆盖的 Redeem"
            " 置灰原因包括没有持有 shares 和 Redeem 数量超过余额; Paused 原因需要 PM 或"
            " 平台文档继续补充。"
        ),
        keywords=("paused", "暂停", "不能 redeem", "redeem 受限", "为什么不能赎回"),
        boundary=True,
    ),
)


def search_platform_faq(query: str, top_k: int) -> list[dict[str, Any]]:
    """Return bounded FAQ chunks matching a platform-mechanism query."""
    if top_k <= 0:
        return []
    normalized_query = _normalize(query)
    if not normalized_query:
        return []

    scored: list[tuple[int, int, PlatformFAQEntry]] = []
    for index, entry in enumerate(_FAQ_ENTRIES):
        score = _score_entry(entry, normalized_query)
        if score > 0:
            scored.append((score, index, entry))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [
        _to_chunk(entry, index=index, score=score)
        for score, index, entry in scored[:top_k]
    ]


def _score_entry(entry: PlatformFAQEntry, normalized_query: str) -> int:
    score = 0
    normalized_question = _normalize(entry.question)
    if len(normalized_query) >= 4 and (
        normalized_query in normalized_question
        or normalized_question in normalized_query
    ):
        score += 4
    for keyword in entry.keywords:
        if _contains_keyword(normalized_query, keyword):
            score += 5 if entry.boundary else 3
    return score


def _contains_keyword(normalized_query: str, keyword: str) -> bool:
    normalized_keyword = _normalize(keyword)
    if not normalized_keyword:
        return False
    if _is_ascii_word(normalized_keyword):
        return normalized_keyword in _ASCII_TOKEN_RE.findall(normalized_query)
    return normalized_keyword in normalized_query


def _is_ascii_word(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9_]+", value))


def _to_chunk(entry: PlatformFAQEntry, *, index: int, score: int) -> dict[str, Any]:
    return {
        "chunk_id": f"{_DOCUMENT_ID}:{entry.id}",
        "document_id": _DOCUMENT_ID,
        "knowledge_base_id": _KNOWLEDGE_BASE_ID,
        "title": f"Agent Protocol FAQ V1 - {entry.section}",
        "content": f"Q: {entry.question}\nA: {entry.answer}",
        "score": float(score),
        "citation": {
            "source_uri": _SOURCE_URI,
            "page": None,
            "section": entry.section,
            "chunk_index": index,
        },
        "metadata": {
            "source": _DOCUMENT_ID,
            "faq_id": entry.id,
            "section": entry.section,
            "boundary": entry.boundary,
        },
    }


def _normalize(value: str) -> str:
    return " ".join(str(value or "").casefold().split())
