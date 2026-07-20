from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from tests.chat_eval.approved_case_workflow import (
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
            ".venv/bin/python",
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
            ".venv/bin/python",
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
