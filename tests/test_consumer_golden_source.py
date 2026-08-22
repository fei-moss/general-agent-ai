from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from app.runtime.marketplace_ai import CONSUMER_DYNAMIC_CONTEXT_FIELDS
from tests.chat_eval.approved_case_workflow import (
    _CONSUMER_DYNAMIC_FIELD_TERMS,
    _contains_forbidden_claim,
    _group_matches,
    _normalize_text,
    build_optimization_report,
    build_preflight_contract,
    build_target_truth_from_marketplace_context,
    load_approved_cases,
    normalize_approved_cases,
)
from tests.chat_eval.consumer_golden_source import parse_consumer_golden_markdown


_EXPECTED_EXCLUSION_BLOCKERS = [
    "兑换码去哪里看？: excluded: source answer is a tester bug note, not an approved ideal answer",
    "兑换码丢了怎么办？: excluded: ideal answer is empty",
    "兑换码可以给别人用吗？: excluded: ideal answer is empty",
    "赎回之后已经拿到的兑换码还能用吗？: excluded: ideal answer is empty",
    "赎回要收费吗？: excluded: ideal answer is empty",
    "持有份额有额外收益吗？: excluded: ideal answer is empty",
    "持有越久越好吗？: excluded: ideal answer is empty",
    "兑换码多久过期？: excluded: ideal answer is empty",
]
_VENDORED_SOURCE = (
    Path(__file__).parent
    / "chat_eval"
    / "fixtures"
    / "consumer_pixverse_golden_source_20260819.md"
)
_VENDORED_SOURCE_SHA256 = (
    "4715696ebba1c743eff0f762ad6e6848f0d513b670c4eb53ba3473dc4149450b"
)


def _write_markdown(tmp_path, body: str):
    source = tmp_path / "consumer-source.md"
    source.write_text(body, encoding="utf-8")
    return source


def _consumer_context(
    *,
    name: str,
    description: str,
    accept_token_symbol: str = "USDC",
) -> dict:
    return {
        "agent": {
            "id": 91,
            "name": name,
            "description": description,
            "agent_type": "consumer",
            "accept_token_symbol": accept_token_symbol,
        },
        "redemption_policy": {
            "available": False,
            "status": "unsupported",
            "reason": "agent_type_unsupported",
        },
        "fee_schedule": {
            "available": False,
            "status": "unsupported",
            "fees": [],
            "reason": "agent_type_unsupported",
        },
    }


def test_vendored_source_batch_is_complete_and_metadata_is_self_consistent():
    payload = _VENDORED_SOURCE.read_bytes()
    parsed = parse_consumer_golden_markdown(_VENDORED_SOURCE)

    assert hashlib.sha256(payload).hexdigest() == _VENDORED_SOURCE_SHA256
    assert len(parsed.rows) == 58
    assert parsed.blockers == _EXPECTED_EXCLUSION_BLOCKERS
    normalized = normalize_approved_cases(
        parsed.rows,
        approved_by="marketplace-product-owner",
        source_version="consumer-pixverse-golden-source-20260819",
    )
    assert len(normalized) == 58
    assert [
        (row["id"], group)
        for row in parsed.rows
        for group in row["required_fact_groups"]
        if not _group_matches(group, row["ideal_answer"])
    ] == []
    assert [
        (row["id"], claim)
        for row in parsed.rows
        for claim in row["forbidden_claims"]
        if _contains_forbidden_claim(row["ideal_answer"], claim)
    ] == []

    by_id = {row["id"]: row for row in parsed.rows}
    assert by_id["pixverse_q11_zh"]["required_fact_groups"] == []
    q07 = by_id["consumer_redemption_q07_zh"]
    assert list(zip(q07["dynamic_fact_variables"], q07["dynamic_fact_rules"])) == [
        ("最低金额", "consumer_minimum_mint_amount"),
        ("Threshold", "consumer_redemption_threshold"),
    ]


def test_consumer_fact_terms_never_normalize_to_only_missing_fact_sentinel():
    rows = parse_consumer_golden_markdown(_VENDORED_SOURCE).rows

    assert [
        (row["id"], group_index, alternative)
        for row in rows
        for group_index, group in enumerate(row["required_fact_groups"])
        for alternative in group
        if _normalize_text(alternative) == "missingfactmarker"
    ] == []


def test_v8_1536_recording_paraphrase_alternatives_are_preserved():
    additions = {
        "consumer_redemption_q01_zh": [(1, "提供的特定服务")],
        "consumer_redemption_q02_zh": [
            (1, "在兑换权益之前"),
            (2, "选择将手中的份额退款"),
        ],
        "consumer_redemption_q03_zh": [
            (0, "用于兑换特定的商品或服务权益"),
            (2, "获取其背后链接的权益"),
        ],
        "consumer_redemption_q04_zh": [(2, "每个份额之间没有区别，可以互换")],
        "consumer_redemption_q05_zh": [(1, "参与确实需要用到加密货币")],
        "consumer_redemption_q08_zh": [(2, "需要您在获得份额后主动发起")],
        "consumer_redemption_q10_zh": [(0, "在创建时都会设定一种固定的代币")],
        "consumer_redemption_q12_zh": [(3, "选择您希望兑换的兑换码数量")],
        "consumer_redemption_q14_zh": [
            (0, "份额一旦成功用于兑换，就会被消耗掉"),
            (1, "被消耗掉，不能再恢复"),
            (2, "不能再恢复或用于赎回"),
        ],
        "consumer_redemption_q15_zh": [
            (2, "会继续由您持有"),
        ],
        "consumer_redemption_q20_zh": [(0, "成功将 Agent 份额兑换成兑换码")],
        "consumer_redemption_q21_zh": [
            (4, "通过当前 Agent 页面上提供的支持方式")
        ],
        "consumer_redemption_q22_zh": [
            (0, "尚未兑换成码的份额"),
            (2, "Refund 功能来拿回资金"),
        ],
        "consumer_redemption_q23_zh": [
            (0, "未消耗的份额"),
            (1, "AI 视频生成码"),
            (2, "这部分份额就被消耗掉了"),
            (3, "不能再被赎回 (Refund)"),
        ],
        "consumer_redemption_q27_zh": [
            (1, "赎回（Refund）操作没有明确的次数限制")
        ],
        "consumer_redemption_q29_zh": [
            (0, "受到智能合约规则的严格限制"),
            (1, "负责管理和维护 Agent"),
            (2, "不能随意动用您投入的资金"),
        ],
        "consumer_redemption_q31_zh": [
            (2, "核心条款在发布时就已确定，并且不能随意更改")
        ],
        "consumer_redemption_q32_zh": [
            (2, "仍然可以通过 Refund 功能按当时的兑换率赎回您的资金")
        ],
        "consumer_redemption_q33_zh": [(1, "从您的钱包转到另一个人的钱包")],
        "consumer_redemption_q34_zh": [
            (2, "用于兑换产品或服务"),
            (3, "不是通过市场交易涨价"),
        ],
        "consumer_redemption_q39_zh": [
            (0, "当前仍然持有"),
            (2, "兑换成代码"),
            (3, "这个余额不包含您已经消耗或兑换成代码的部分"),
        ],
        "consumer_redemption_q40_zh": [
            (1, "显示该 Agent 的 Mint 记录"),
            (3, "显示该 Agent 的换码记录"),
        ],
        "consumer_redemption_q41_zh": [
            (0, "钱包地址中尚未持有该 Agent 的份额")
        ],
        "consumer_redemption_q42_zh": [(5, "已经持有的份额仍然属于您")],
        "consumer_redemption_q43_zh": [
            (1, "这部分份额就会被消耗掉"),
            (2, "不能再用于申请 Refund"),
            (
                3,
                "如果您只兑换了一部分份额，那么剩余未兑换的份额仍然在您这里，"
                "可以用于未来的 Refund 操作",
            ),
        ],
        "consumer_redemption_q44_zh": [(0, "手动发起兑换流程")],
        "consumer_redemption_q45_zh": [(2, "不保本")],
        "pixverse_q01_zh": [
            (1, "研发自己的视频基础模型"),
            (5, "对话式创作"),
        ],
        "pixverse_q04_zh": [
            (0, "人工智能（AI）视频生成公司"),
            (2, "利用区块链技术来完成其品牌权益的付费和兑换结算"),
            (3, "品牌权益的付费和兑换结算"),
        ],
        "pixverse_q16_zh": [
            (3, "PixVerse 权益码"),
            (4, "依赖于 PixVerse 是否按照其条款继续履约"),
        ],
        "pixverse_q17_zh": [(1, "PixVerse AI Agent 的 ERC-20 份额")],
        "pixverse_q18_zh": [(0, "可供兑换的 AI 服务权益")],
    }
    rows = {
        row["id"]: row
        for row in parse_consumer_golden_markdown(_VENDORED_SOURCE).rows
    }

    for case_id, case_additions in additions.items():
        alternatives = [alternative for _, alternative in case_additions]
        assert len(alternatives) == len(set(alternatives)), case_id
        for group_index, alternative in case_additions:
            assert alternative in rows[case_id]["required_fact_groups"][group_index]


def test_adapter_preserves_bare_colon_answer_and_consumer_scope(tmp_path):
    source = _write_markdown(
        tmp_path,
        """# Redemption / PixVerse Agent Golden Cases(owner 提供,2026-08-19)

第一部分：通用 Redemption Agent
Q：这个 agent 是做什么的？
A：它让你把资金放进合约来换取【品牌方】的权益。
Q：和直接在【品牌方】官网买有什么区别？
A：钱进入的是合约，在兑换之前可以取回。
Q：这是投资产品吗？
A：不是。这是一个换取权益的工具。
Q：这是 NFT 吗？
A：不是。份额是标准的 ERC-20 代币。
Q：我需要懂加密货币才能用吗？
A：需要一个钱包和对应的结算代币。
Q：怎么开始？
 ：连接钱包，在 Mint 区输入金额，提交申请。结算完成后份额会变为可领取，领取后就出现在 My Shares 里。
""",
    )

    parsed = parse_consumer_golden_markdown(source)

    assert parsed.blockers == []
    assert parsed.rows[-1]["id"] == "consumer_redemption_q06_zh"
    assert parsed.rows[-1]["question"] == "怎么开始？"
    assert parsed.rows[-1]["ideal_answer"] == (
        "连接钱包，在 Mint 区输入金额，提交申请。结算完成后份额会变为可领取，"
        "领取后就出现在 My Shares 里。"
    )
    assert parsed.rows[-1]["locale"] == "zh"
    assert parsed.rows[-1]["applicable_agent_types"] == ["consumer"]
    assert parsed.rows[-1]["tags"] == [
        "consumer",
        "redemption",
        "consumer_redemption_overview",
        "zh",
    ]


def test_adapter_reports_all_eight_exclusions_and_cli_exits_one(tmp_path):
    source = _write_markdown(
        tmp_path,
        """第一部分：通用 Redemption Agent
Q：兑换码去哪里看？
A：这个目前测试的时候，找不到地方点击回查看兑换码
Q：兑换码丢了怎么办？
A：
Q：兑换码可以给别人用吗？
A：
Q：赎回之后已经拿到的兑换码还能用吗？
A：
Q：赎回要收费吗？
A：
Q：持有份额有额外收益吗？
A：
Q：持有越久越好吗？
A：
Q：兑换码多久过期？
A：
""",
    )
    output = tmp_path / "rows.jsonl"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.chat_eval.consumer_golden_source",
            "--input",
            str(source),
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert output.read_text(encoding="utf-8") == ""
    assert json.loads(completed.stdout) == {
        "blockers": _EXPECTED_EXCLUSION_BLOCKERS,
        "rows": 0,
    }


def test_adapter_extracts_placeholders_and_marks_pixverse_brand_scope(tmp_path):
    source = _write_markdown(
        tmp_path,
        """第一部分：通用 Redemption Agent
Q：这个 agent 是做什么的？
A：它让你把资金放进合约来换取【品牌方】的权益。

第二部分：PixVerse Agent 专属
一、关于 PixVerse
Q：PixVerse 是什么？
A：一家 AI 视频生成公司。
Q：它的模型好吗？
A：榜单会更新，建议以最新为准。
Q：为什么选 PixVerse 合作？
A：因为它是用户本来就想买的东西。
Q：PixVerse 是加密项目吗？
A：不是。它是一家 AI 公司。
二、权益本身
Q：兑换码能换到什么？
A：【具体权益，如 X 个 credits / X 分钟生成时长 / X 个月订阅】。
""",
    )

    parsed = parse_consumer_golden_markdown(source)

    assert parsed.blockers == []
    generic = parsed.rows[0]
    assert generic["dynamic_fact_variables"] == ["品牌方"]
    assert generic["dynamic_fact_rules"] == ["consumer_brand_name"]
    pixverse = parsed.rows[-1]
    assert pixverse["id"] == "pixverse_q05_zh"
    assert pixverse["dynamic_fact_variables"] == [
        "具体权益，如 X 个 credits / X 分钟生成时长 / X 个月订阅"
    ]
    assert pixverse["dynamic_fact_rules"] == ["consumer_redemption_benefit"]
    assert pixverse["applicable_agent_types"] == ["consumer"]
    assert pixverse["applicable_agent_brands"] == ["pixverse"]
    assert pixverse["tags"] == [
        "consumer",
        "redemption",
        "pixverse_benefit",
        "zh",
        "pixverse",
        "brand:pixverse",
    ]


def test_consumer_rows_round_trip_through_existing_approved_ingest_cli(tmp_path):
    source = _write_markdown(
        tmp_path,
        """第一部分：通用 Redemption Agent
Q：这个 agent 是做什么的？
A：它让你把资金放进合约来换取【品牌方】的权益。
""",
    )
    adapted = tmp_path / "adapted.jsonl"
    cases = tmp_path / "cases.jsonl"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.chat_eval.consumer_golden_source",
            "--input",
            str(source),
            "--output",
            str(adapted),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.chat_eval.approved_case_workflow",
            "ingest",
            "--input",
            str(adapted),
            "--output",
            str(cases),
            "--approved-by",
            "marketplace-product-owner",
            "--source-version",
            "consumer-pixverse-golden-source-20260819",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    loaded = load_approved_cases(cases)
    assert len(loaded) == 1
    assert loaded[0]["id"] == "consumer_redemption_q01_zh"
    assert loaded[0]["source_question_id"] == "redemption-Q1"
    assert loaded[0]["dynamic_fact_variables"] == ["品牌方"]
    assert loaded[0]["dynamic_fact_rules"] == ["consumer_brand_name"]
    assert loaded[0]["approval"]["source_version"] == (
        "consumer-pixverse-golden-source-20260819"
    )


def test_consumer_preflight_blocks_when_external_dynamic_truth_is_absent(tmp_path):
    source = _write_markdown(
        tmp_path,
        """第一部分：通用 Redemption Agent
Q：这个 agent 是做什么的？
A：它让你把资金放进合约来换取【品牌方】的权益。
Q：和直接在【品牌方】官网买有什么区别？
A：钱进入的是合约，在兑换之前可以取回。
Q：这是投资产品吗？
A：不是。这是一个换取权益的工具。
Q：这是 NFT 吗？
A：不是。份额是标准的 ERC-20 代币。
Q：我需要懂加密货币才能用吗？
A：需要一个钱包和对应的结算代币。
Q：怎么开始？
 ：连接钱包，在 Mint 区输入金额，提交申请。
Q：最少要 mint 多少？
A：【最低金额】。兑换码需要达到【Threshold】份额才能换一个。
""",
    )
    row = parse_consumer_golden_markdown(source).rows[-1]
    cases = normalize_approved_cases(
        [row],
        approved_by="marketplace-product-owner",
        source_version="consumer-pixverse-golden-source-20260819",
    )

    truth = build_target_truth_from_marketplace_context(
        _consumer_context(
            name="PixVerse Redemption",
            description="Redeem shares for PixVerse benefits.",
        )
    )
    preflight = build_preflight_contract(cases, target_truth=truth)

    assert set(CONSUMER_DYNAMIC_CONTEXT_FIELDS) == set(
        _CONSUMER_DYNAMIC_FIELD_TERMS
    )
    assert set(CONSUMER_DYNAMIC_CONTEXT_FIELDS) >= {
        "consumer_minimum_mint_amount",
        "consumer_redemption_threshold",
        "consumer_mint_fee",
        "consumer_refund_fee",
        "consumer_accept_token",
    }
    assert "门槛" in _CONSUMER_DYNAMIC_FIELD_TERMS[
        "consumer_redemption_threshold"
    ]
    assert "铸造费" in _CONSUMER_DYNAMIC_FIELD_TERMS["consumer_mint_fee"]
    assert "赎回费" in _CONSUMER_DYNAMIC_FIELD_TERMS["consumer_refund_fee"]
    assert "结算代币" in _CONSUMER_DYNAMIC_FIELD_TERMS["consumer_accept_token"]
    assert "兑换码价值" in _CONSUMER_DYNAMIC_FIELD_TERMS[
        "consumer_redemption_code_value"
    ]
    assert "支持渠道" in _CONSUMER_DYNAMIC_FIELD_TERMS[
        "consumer_official_support_channel"
    ]
    assert truth["agent_brands"] == ["pixverse"]
    assert truth["dynamic_facts"]["consumer_brand_name"][
        "required_fact_groups"
    ] == [["PixVerse", *_CONSUMER_DYNAMIC_FIELD_TERMS["consumer_brand_name"]]]
    assert truth["dynamic_facts"]["consumer_accept_token"][
        "required_fact_groups"
    ] == [["USDC"]]
    assert "consumer_minimum_mint_amount" not in truth["dynamic_facts"]
    assert "consumer_redemption_threshold" not in truth["dynamic_facts"]
    assert preflight["status"] == "blocked"
    assert preflight["live_run_allowed"] is False
    assert preflight["blockers"] == [
        "dynamic target truth missing for "
        "['consumer_minimum_mint_amount', 'consumer_redemption_threshold']"
    ]


def test_consumer_dynamic_value_and_generic_term_semantics():
    brand_case, token_case = normalize_approved_cases(
        [
            {
                "id": "consumer-brand",
                "question": "Who supplies the benefit?",
                "ideal_answer": "The brand supplies it.",
                "required_fact_groups": [],
                "dynamic_fact_rules": ["consumer_brand_name"],
                "applicable_agent_types": ["consumer"],
            },
            {
                "id": "consumer-token",
                "question": "Which token does this Agent accept?",
                "ideal_answer": "Use the current accepted token.",
                "required_fact_groups": [],
                "dynamic_fact_rules": ["consumer_accept_token"],
                "applicable_agent_types": ["consumer"],
            },
        ],
        approved_by="marketplace-product-owner",
        source_version="consumer-pixverse-golden-source-20260819",
    )
    truth = build_target_truth_from_marketplace_context(
        _consumer_context(
            name="PixVerse Redemption",
            description="Redeem shares for PixVerse benefits.",
            accept_token_symbol="bnbUSDC",
        )
    )

    def hard_pass(case, answer: str) -> bool:
        report = build_optimization_report(
            [case],
            {
                "status": "passed",
                "results": [
                    {
                        "case_id": case["id"],
                        "status": "completed",
                        "content": answer,
                        "tool_calls": ["marketplace_agent_context"],
                    }
                ],
            },
            target_truth=truth,
        )
        return report["case_results"][0]["hard_pass"]

    assert hard_pass(brand_case, "权益由品牌方提供。") is True
    assert hard_pass(brand_case, "权益由 PixVerse 提供。") is True
    assert hard_pass(token_case, "请使用页面显示的结算代币。") is False
    assert hard_pass(token_case, "请使用 bnbUSDC。") is True


def test_pixverse_cases_are_not_applicable_to_other_consumer_brands(tmp_path):
    source = _write_markdown(
        tmp_path,
        """第二部分：PixVerse Agent 专属
一、关于 PixVerse
Q：PixVerse 是什么？
A：一家 AI 视频生成公司，做自研的视频基础模型。
""",
    )
    row = parse_consumer_golden_markdown(source).rows[0]
    cases = normalize_approved_cases(
        [row],
        approved_by="marketplace-product-owner",
        source_version="consumer-pixverse-golden-source-20260819",
    )

    truth = build_target_truth_from_marketplace_context(
        _consumer_context(
            name="Another Brand Redemption",
            description="Redeem shares for another service.",
        )
    )
    preflight = build_preflight_contract(cases, target_truth=truth)

    assert truth["agent_brands"] == []
    assert preflight["status"] == "ready"
    assert preflight["case_ids"] == []
    assert preflight["fact_matrix"][0]["applicable"] is False
    assert preflight["fact_matrix"][0]["applicable_agent_brands"] == ["pixverse"]
    other_type_preflight = build_preflight_contract(
        cases,
        target_truth={"agent_type": "hyperliquid", "dynamic_facts": {}},
    )
    assert "target_agent_brands" not in other_type_preflight
    report = build_optimization_report(
        cases,
        {"status": "passed", "results": []},
        target_truth=truth,
    )
    assert report["summary"]["not_applicable_count"] == 1
    assert report["case_results"][0]["status"] == "not_applicable"


def test_pixverse_report_does_not_treat_missing_typed_scope_as_not_applicable(
    tmp_path,
):
    source = _write_markdown(
        tmp_path,
        """第二部分：PixVerse Agent 专属
一、关于 PixVerse
Q：PixVerse 是什么？
A：一家 AI 视频生成公司，做自研的视频基础模型。
""",
    )
    cases = normalize_approved_cases(
        [parse_consumer_golden_markdown(source).rows[0]],
        approved_by="marketplace-product-owner",
        source_version="consumer-pixverse-golden-source-20260819",
    )

    report = build_optimization_report(
        cases,
        {"status": "passed", "results": []},
        target_truth=None,
    )

    assert report["status"] == "blocked"
    assert report["summary"]["not_applicable_count"] == 0
    assert report["case_results"][0]["target_agent_type_missing"] is True
