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
