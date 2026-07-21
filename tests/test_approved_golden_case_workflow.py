from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.chat_eval.approved_case_workflow import (
    build_target_truth_from_marketplace_context,
    build_optimization_report,
    load_approved_cases,
    normalize_approved_cases,
    write_jsonl,
)
from tests.chat_eval.evaluator import load_cases


def _source_case(**overrides):
    row = {
        "id": "marketplace_mint_meaning_zh",
        "question": "Mint 一个 Agent 的份额是什么意思？",
        "ideal_answer": "Mint 会获得 Agent 的链上份额，份额价值会随 Agent 管理资产变化。",
        "locale": "zh",
        "area": "marketplace",
        "required_fact_groups": [
            ["链上份额", "Agent 份额"],
            ["份额价值", "份额价格"],
        ],
        "forbidden_claims": ["固定收益"],
        "requires_rag": True,
        "requires_tool": None,
        "risk_level": "high",
        "quality_axes": ["correctness", "data_faithfulness"],
        "tags": ["mint", "marketplace"],
    }
    row.update(overrides)
    return row


def _live_report(answer: str, *, status: str = "completed") -> dict:
    return {
        "status": "passed",
        "results": [
            {
                "case_id": "marketplace_mint_meaning_zh",
                "status": status,
                "content": answer,
                "tool_calls": [],
            }
        ],
    }


def _target_truth(**overrides):
    truth = {
        "agent_type": "hyperliquid",
        "dynamic_facts": {
            "current_agent_redemption_policy": {
                "required_fact_groups": [
                    ["2 hours 46 minutes", "2h 46m", "2 小时 46 分钟"],
                    ["claim", "领取"],
                ],
                "forbidden_claims": ["no lock-up", "没有锁定期"],
            },
            "current_agent_fee_schedule": {
                "required_fact_groups": [
                    ["management fee", "management_fee", "管理费"],
                    ["1%"],
                ],
                "forbidden_claims": [],
            },
        },
    }
    truth.update(overrides)
    return truth


def _marketplace_context(**overrides):
    context = {
        "agent": {"id": 26, "name": "Agent", "agent_type": "hyperliquid"},
        "redemption_policy": {
            "available": True,
            "status": "ok",
            "lock_period_seconds": 10000,
            "claim_required": True,
            "settlement_required": True,
            "source": "onchain_contract_read",
            "reason": None,
        },
        "fee_schedule": {
            "available": True,
            "status": "ok",
            "fees": [
                {
                    "fee_type": "management_fee",
                    "rate_bps": 100,
                    "source": "onchain_contract_read",
                }
            ],
            "source": "onchain_contract_read",
            "reason": None,
        },
    }
    context.update(overrides)
    return context


def test_normalize_preserves_approved_reference_and_is_evaluator_compatible(tmp_path):
    rows = normalize_approved_cases(
        [_source_case()],
        approved_by="marketplace-product-owner",
        source_version="ops-golden-2026-07-20-v1",
    )

    assert rows[0]["user_message"] == "Mint 一个 Agent 的份额是什么意思？"
    assert rows[0]["ideal_answer"].startswith("Mint 会获得")
    assert rows[0]["approval"] == {
        "status": "approved",
        "approved_by": "marketplace-product-owner",
        "source_version": "ops-golden-2026-07-20-v1",
    }
    assert rows[0]["answer_traits"] == ["链上份额", "份额价值"]

    output = tmp_path / "approved_cases.jsonl"
    write_jsonl(rows, output)
    loaded = load_cases(output)
    assert loaded[0].id == "marketplace_mint_meaning_zh"


def test_normalize_preserves_agent_type_and_dynamic_fact_rules():
    rows = normalize_approved_cases(
        [
            _source_case(
                applicable_agent_types=["Hyperliquid"],
                dynamic_fact_rules=["current_agent_fee_schedule"],
                requires_rag=True,
                requires_tool="marketplace_agent_context",
            )
        ],
        approved_by="product-owner",
        source_version="ask-this-agent-presets-v1",
    )

    assert rows[0]["applicable_agent_types"] == ["hyperliquid"]
    assert rows[0]["dynamic_fact_rules"] == ["current_agent_fee_schedule"]
    assert rows[0]["requires_tool"] == "marketplace_agent_context"


def test_normalize_requires_owner_approval_and_structured_hard_facts():
    with pytest.raises(ValueError, match="approved_by"):
        normalize_approved_cases(
            [_source_case()], approved_by="", source_version="ops-v1"
        )

    with pytest.raises(ValueError, match="required_fact_groups"):
        normalize_approved_cases(
            [_source_case(required_fact_groups=[])],
            approved_by="product-owner",
            source_version="ops-v1",
        )


def test_normalize_is_idempotent_and_rejects_conflicting_case_ids():
    rows = normalize_approved_cases(
        [_source_case(), _source_case()],
        approved_by="product-owner",
        source_version="ops-v1",
    )
    assert len(rows) == 1

    with pytest.raises(ValueError, match="conflicting duplicate id"):
        normalize_approved_cases(
            [_source_case(), _source_case(ideal_answer="另一个已确认答案")],
            approved_by="product-owner",
            source_version="ops-v1",
        )


def test_unchanged_case_can_reappear_in_a_later_approved_batch():
    existing = normalize_approved_cases(
        [_source_case()],
        approved_by="product-owner",
        source_version="ops-v1",
    )
    merged = normalize_approved_cases(
        [_source_case()],
        approved_by="product-owner",
        source_version="ops-v2",
        existing_rows=existing,
    )

    assert merged == existing


def test_approved_case_can_have_no_forbidden_claims(tmp_path):
    rows = normalize_approved_cases(
        [_source_case(forbidden_claims=[])],
        approved_by="product-owner",
        source_version="ops-v1",
    )
    output = tmp_path / "approved_cases.jsonl"
    write_jsonl(rows, output)

    assert rows[0]["forbidden_claims"] == []
    assert load_cases(output)[0].id == "marketplace_mint_meaning_zh"


def test_normalized_jsonl_loader_accepts_multiple_incremental_cases(tmp_path):
    rows = normalize_approved_cases(
        [
            _source_case(),
            _source_case(
                id="marketplace_redeem_meaning_zh",
                question="Redeem 是什么意思？",
                ideal_answer="Redeem 是赎回 Agent 份额。",
                required_fact_groups=[["赎回"], ["Agent 份额"]],
                tags=["redeem", "marketplace"],
            ),
        ],
        approved_by="product-owner",
        source_version="ops-v1",
    )
    output = tmp_path / "approved_cases.jsonl"
    write_jsonl(rows, output)

    assert [row["id"] for row in load_approved_cases(output)] == [
        "marketplace_mint_meaning_zh",
        "marketplace_redeem_meaning_zh",
    ]


def test_refusal_case_requires_an_explicit_guardrail_category():
    with pytest.raises(ValueError, match="expected_input_category"):
        normalize_approved_cases(
            [_source_case(expected_input_action="refuse")],
            approved_by="product-owner",
            source_version="ops-v1",
        )


def test_load_approved_cases_rejects_non_approved_rows(tmp_path):
    output = tmp_path / "cases.jsonl"
    output.write_text(
        json.dumps(
            {
                **normalize_approved_cases(
                    [_source_case()],
                    approved_by="product-owner",
                    source_version="ops-v1",
                )[0],
                "approval": {"status": "pending"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="product-owner approved"):
        load_approved_cases(output)


def test_report_keeps_coverage_informational_and_emits_semantic_review_packet():
    cases = normalize_approved_cases(
        [_source_case()],
        approved_by="product-owner",
        source_version="ops-v1",
    )
    report = build_optimization_report(
        cases,
        _live_report("Mint 后会获得 Agent 份额，份额价格随管理资产变化。"),
    )

    assert report["status"] == "needs_semantic_review"
    assert report["summary"]["hard_failure_count"] == 0
    assert report["summary"]["semantic_pending_count"] == 1
    assert report["release_blockers"] == []
    assert report["coverage"]["areas"] == {"marketplace": 1}
    assert "gaps" not in report["coverage"]
    assert report["semantic_review_packet"][0]["ideal_answer"].startswith(
        "Mint 会获得"
    )


def test_report_blocks_missing_hard_fact_and_attributes_rag_gap():
    cases = normalize_approved_cases(
        [_source_case()],
        approved_by="product-owner",
        source_version="ops-v1",
    )
    report = build_optimization_report(
        cases,
        _live_report("Mint 是一个页面操作，具体以页面为准。"),
    )

    assert report["status"] == "blocked"
    assert report["summary"]["hard_failure_count"] == 1
    assert report["release_blockers"]
    result = report["case_results"][0]
    assert result["missing_fact_groups"] == [
        ["链上份额", "Agent 份额"],
        ["份额价值", "份额价格"],
    ]
    assert result["suggested_attribution"] == "rag_or_retrieval"


def test_report_skips_cases_outside_the_target_agent_type():
    cases = normalize_approved_cases(
        [_source_case(applicable_agent_types=["hyperliquid"])],
        approved_by="product-owner",
        source_version="ops-v1",
    )

    report = build_optimization_report(
        cases,
        {"status": "passed", "results": []},
        target_truth=_target_truth(agent_type="ballot"),
    )

    assert report["status"] == "passed"
    assert report["summary"]["case_count"] == 0
    assert report["summary"]["not_applicable_count"] == 1
    assert report["case_results"][0]["status"] == "not_applicable"


def test_report_blocks_when_agent_type_scoping_has_no_target_type():
    cases = normalize_approved_cases(
        [_source_case(applicable_agent_types=["hyperliquid"])],
        approved_by="product-owner",
        source_version="ops-v1",
    )

    report = build_optimization_report(cases, _live_report("Agent 份额价值会变化。"))

    assert report["status"] == "blocked"
    assert report["case_results"][0]["target_agent_type_missing"] is True
    assert "target agent type missing" in report["release_blockers"][0]


def test_report_requires_target_truth_for_dynamic_facts():
    cases = normalize_approved_cases(
        [_source_case(dynamic_fact_rules=["current_agent_redemption_policy"])],
        approved_by="product-owner",
        source_version="ops-v1",
    )

    report = build_optimization_report(cases, _live_report("Redeem 后领取资产。"))

    assert report["status"] == "blocked"
    assert report["case_results"][0]["missing_dynamic_rules"] == [
        "current_agent_redemption_policy"
    ]
    assert "dynamic target truth missing" in report["release_blockers"][0]


def test_report_uses_current_agent_truth_instead_of_static_ideal_answer():
    cases = normalize_approved_cases(
        [
            _source_case(
                id="marketplace_mint_meaning_zh",
                required_fact_groups=[["赎回", "redeem"]],
                dynamic_fact_rules=["current_agent_redemption_policy"],
            )
        ],
        approved_by="product-owner",
        source_version="ops-v1",
    )

    passed = build_optimization_report(
        cases,
        _live_report("可以 redeem；锁定期是 2 小时 46 分钟，之后需要领取 claim。"),
        target_truth=_target_truth(),
    )
    failed = build_optimization_report(
        cases,
        _live_report("可以随时 redeem，没有锁定期。"),
        target_truth=_target_truth(),
    )

    assert passed["case_results"][0]["hard_pass"] is True
    review_item = passed["semantic_review_packet"][0]
    assert review_item["dynamic_fact_rules"] == [
        "current_agent_redemption_policy"
    ]
    assert review_item["target_truth"]["current_agent_redemption_policy"]
    assert "overrides the static ideal answer" in review_item["instruction"]
    assert failed["case_results"][0]["hard_pass"] is False
    assert failed["case_results"][0]["forbidden_hits"] == ["没有锁定期"]


def test_report_checks_current_agent_fee_names_and_rates():
    cases = normalize_approved_cases(
        [
            _source_case(
                required_fact_groups=[["fee", "费用"]],
                dynamic_fact_rules=["current_agent_fee_schedule"],
            )
        ],
        approved_by="product-owner",
        source_version="ops-v1",
    )

    report = build_optimization_report(
        cases,
        _live_report("This Agent charges a 1% Management Fee."),
        target_truth=_target_truth(),
    )

    assert report["case_results"][0]["hard_pass"] is True


def test_percentage_fact_does_not_match_a_numbered_list_item():
    cases = normalize_approved_cases(
        [
            _source_case(
                required_fact_groups=[["fee", "费用"]],
                dynamic_fact_rules=["current_agent_fee_schedule"],
            )
        ],
        approved_by="product-owner",
        source_version="ops-v1",
    )

    report = build_optimization_report(
        cases,
        _live_report("1. Management Fee: the exact rate is unavailable."),
        target_truth=_target_truth(),
    )

    assert report["case_results"][0]["hard_pass"] is False
    assert ["management fee", "management_fee", "管理费"] not in report[
        "case_results"
    ][0]["missing_fact_groups"]
    assert ["1%"] in report["case_results"][0]["missing_fact_groups"]


def test_fee_truth_rejects_unreturned_collection_mechanics():
    cases = normalize_approved_cases(
        [
            _source_case(
                required_fact_groups=[["fee", "费用"]],
                dynamic_fact_rules=["current_agent_fee_schedule"],
            )
        ],
        approved_by="product-owner",
        source_version="ops-v1",
    )
    truth = build_target_truth_from_marketplace_context(_marketplace_context())

    report = build_optimization_report(
        cases,
        _live_report(
            "Management Fee is 1% per annum. "
            "No other fee types are currently configured."
        ),
        target_truth=truth,
    )

    assert report["case_results"][0]["hard_pass"] is False
    assert report["case_results"][0]["forbidden_hits"] == [
        "per annum",
        "no other fee types are currently configured",
    ]


def test_build_target_truth_uses_typed_marketplace_dynamic_config():
    truth = build_target_truth_from_marketplace_context(_marketplace_context())

    assert truth["agent_type"] == "hyperliquid"
    redemption = truth["dynamic_facts"]["current_agent_redemption_policy"]
    lock_terms = redemption["required_fact_groups"][0]
    assert "10000 seconds" in lock_terms
    assert "10,000 seconds" in lock_terms
    assert "2h 46m 40s" in lock_terms
    assert "2 hours, 46 minutes, and 40 seconds" in lock_terms
    assert "2小时46分钟40秒" in lock_terms
    assert ["claim", "领取", "申领"] in redemption["required_fact_groups"]
    assert ["settlement", "结算"] in redemption["required_fact_groups"]
    assert "no lock-up" in redemption["forbidden_claims"]
    assert "settles positions" in redemption["forbidden_claims"]
    assert "close out your portion" in redemption["forbidden_claims"]

    fees = truth["dynamic_facts"]["current_agent_fee_schedule"]
    assert ["management fee", "management_fee", "管理费"] in fees[
        "required_fact_groups"
    ]
    rate_terms = fees["required_fact_groups"][1]
    assert "100 bps" in rate_terms
    assert "1%" in rate_terms
    assert "1.0%" in rate_terms
    assert "1 percent" in rate_terms
    assert "annualized" in fees["forbidden_claims"]
    assert "per annum" in fees["forbidden_claims"]
    assert "年化" in fees["forbidden_claims"]
    assert "从持仓中扣除" in fees["forbidden_claims"]
    assert "no other fee types are currently configured" in fees[
        "forbidden_claims"
    ]
    assert all("mint fee" not in group for group in fees["required_fact_groups"])


def test_build_target_truth_preserves_explicit_zero_and_unavailable_states():
    zero = build_target_truth_from_marketplace_context(
        _marketplace_context(
            redemption_policy={
                "available": True,
                "status": "ok",
                "lock_period_seconds": 0,
                "claim_required": False,
                "settlement_required": False,
                "source": "onchain_contract_read",
                "reason": None,
            },
            fee_schedule={
                "available": True,
                "status": "ok",
                "fees": [
                    {
                        "fee_type": "management_fee",
                        "rate_bps": 0,
                        "source": "onchain_contract_read",
                    }
                ],
                "source": "onchain_contract_read",
                "reason": None,
            },
        )
    )
    unavailable = build_target_truth_from_marketplace_context(
        _marketplace_context(
            redemption_policy={
                "available": False,
                "status": "unavailable",
                "lock_period_seconds": None,
                "claim_required": None,
                "settlement_required": None,
                "source": None,
                "reason": "authoritative_source_unavailable",
            },
            fee_schedule={
                "available": False,
                "status": "unsupported",
                "fees": [],
                "source": None,
                "reason": "contract_interface_unsupported",
            },
        )
    )

    zero_redemption = zero["dynamic_facts"]["current_agent_redemption_policy"]
    assert ["0 seconds", "0 秒", "no lock-up", "没有锁定期"] in zero_redemption[
        "required_fact_groups"
    ]
    assert zero_redemption["forbidden_claims"] == [
        "settles positions",
        "close out your portion",
        "close positions as needed",
        "平仓结算",
    ]
    zero_rate_terms = zero["dynamic_facts"]["current_agent_fee_schedule"][
        "required_fact_groups"
    ][1]
    assert "0 bps" in zero_rate_terms
    assert "0%" in zero_rate_terms
    assert "0.0%" in zero_rate_terms
    assert ["unavailable", "暂不可用", "无法获取"] in unavailable[
        "dynamic_facts"
    ]["current_agent_redemption_policy"]["required_fact_groups"]
    assert ["unsupported", "不支持", "未提供"] in unavailable["dynamic_facts"][
        "current_agent_fee_schedule"
    ]["required_fact_groups"]


def test_build_target_truth_rejects_malformed_marketplace_config():
    with pytest.raises(ValueError, match="lock_period_seconds"):
        build_target_truth_from_marketplace_context(
            _marketplace_context(
                redemption_policy={
                    "available": True,
                    "status": "ok",
                    "lock_period_seconds": None,
                    "claim_required": True,
                    "settlement_required": True,
                }
            )
        )

    with pytest.raises(ValueError, match="unsupported fee_type"):
        build_target_truth_from_marketplace_context(
            _marketplace_context(
                fee_schedule={
                    "available": True,
                    "status": "ok",
                    "fees": [{"fee_type": "ui_mint_label", "rate_bps": 100}],
                }
            )
        )


def test_report_treats_semantic_judge_as_advisory_but_tracks_optimization():
    cases = normalize_approved_cases(
        [_source_case(risk_level="low")],
        approved_by="product-owner",
        source_version="ops-v1",
    )
    semantic_reviews = [
        {
            "case_id": "marketplace_mint_meaning_zh",
            "verdict": "gap",
            "reason": "回答遗漏了份额价值为何变化的解释。",
            "gaps": ["解释份额价值与 Agent 管理资产的关系"],
            "attribution": "prompt_or_answer_composition",
            "dimension_scores": {"correctness": 2, "completeness": 1},
        }
    ]
    report = build_optimization_report(
        cases,
        _live_report("Mint 会获得链上份额，份额价值以页面为准。"),
        semantic_reviews=semantic_reviews,
    )

    assert report["status"] == "needs_optimization"
    assert report["release_blockers"] == []
    assert report["summary"]["semantic_gap_count"] == 1
    assert report["case_results"][0]["suggested_attribution"] == (
        "prompt_or_answer_composition"
    )


def test_report_accepts_reviewed_variance_without_overfitting():
    cases = normalize_approved_cases(
        [_source_case(risk_level="low")],
        approved_by="product-owner",
        source_version="ops-v1",
    )
    semantic_reviews = [
        {
            "case_id": "marketplace_mint_meaning_zh",
            "verdict": "accepted_variance",
            "reason": "措辞不同但业务语义完整。",
            "gaps": [],
            "attribution": "none",
            "dimension_scores": {"correctness": 2, "completeness": 2},
        }
    ]
    report = build_optimization_report(
        cases,
        _live_report("Mint 会获得 Agent 份额，份额价格随管理资产变化。"),
        semantic_reviews=semantic_reviews,
    )

    assert report["status"] == "passed"
    assert report["completion_blockers"] == []


def test_high_risk_semantic_gap_is_a_completion_blocker_not_release_blocker():
    cases = normalize_approved_cases(
        [_source_case()],
        approved_by="product-owner",
        source_version="ops-v1",
    )
    semantic_reviews = [
        {
            "case_id": "marketplace_mint_meaning_zh",
            "verdict": "gap",
            "reason": "高风险业务解释仍不完整。",
            "gaps": ["风险解释"],
            "attribution": "prompt_or_answer_composition",
            "dimension_scores": {"correctness": 2, "completeness": 1},
        }
    ]
    report = build_optimization_report(
        cases,
        _live_report("Mint 会获得 Agent 份额，份额价格随管理资产变化。"),
        semantic_reviews=semantic_reviews,
    )

    assert report["status"] == "needs_optimization"
    assert report["release_blockers"] == []
    assert report["completion_blockers"] == [
        "marketplace_mint_meaning_zh: high-risk semantic gap"
    ]


def test_live_runner_accepts_an_explicit_case_file_contract():
    source = Path("tests/chat_eval/live_runner.py").read_text(encoding="utf-8")
    assert '"--case-file",' in source
    assert "load_cases(args.case_file)" in source


def test_cli_round_trip_builds_reviewable_optimization_report(tmp_path):
    source = tmp_path / "source.jsonl"
    cases = tmp_path / "cases.jsonl"
    baseline = tmp_path / "baseline.json"
    report = tmp_path / "report.json"
    source.write_text(json.dumps(_source_case(), ensure_ascii=False) + "\n", encoding="utf-8")
    baseline.write_text(
        json.dumps(
            _live_report("Mint 会获得 Agent 份额，份额价格随管理资产变化。"),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.chat_eval.approved_case_workflow",
            "ingest",
            "--input",
            str(source),
            "--output",
            str(cases),
            "--approved-by",
            "product-owner",
            "--source-version",
            "ops-v1",
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
            "report",
            "--cases",
            str(cases),
            "--baseline",
            str(baseline),
            "--output",
            str(report),
            "--strict-hard",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "needs_semantic_review"
    assert payload["release_blockers"] == []
    assert payload["semantic_review_packet"][0]["judge_mode"] == (
        "llm_judge_advisory"
    )


def test_cli_derives_sanitized_target_truth_from_marketplace_context(tmp_path):
    context = tmp_path / "context.json"
    output = tmp_path / "target-truth.json"
    context.write_text(json.dumps(_marketplace_context()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.chat_eval.approved_case_workflow",
            "target-truth",
            "--context",
            str(context),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    serialized = json.dumps(payload)
    assert payload["agent_type"] == "hyperliquid"
    assert "10000 seconds" in serialized
    assert "management fee" in serialized
    assert "Lock Period Test" not in serialized


def test_runbook_keeps_intake_incremental_and_code_changes_controlled():
    runbook = Path("docs/APPROVED_GOLDEN_CASE_WORKFLOW.md").read_text(
        encoding="utf-8"
    )

    assert "tests.chat_eval.approved_case_workflow ingest" in runbook
    assert "tests.chat_eval.approved_case_workflow report" in runbook
    assert "tests.chat_eval.live_runner" in runbook
    assert "产品负责人已确认" in runbook
    assert "不要求穷举完整业务覆盖" in runbook
    assert "不会自动修改 Prompt、运行时代码或生产配置" in runbook
    assert "accepted_variance" in runbook
