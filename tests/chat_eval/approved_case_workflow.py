"""Approved Golden Case intake and optimization-gap reporting.

The workflow deliberately separates deterministic release blockers from
advisory semantic review. It never mutates runtime, prompts, or product code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from app.runtime.marketplace_ai import BALLOT_DYNAMIC_CONTEXT_FIELDS
from tests.chat_eval.evaluator import validate_cases


SCHEMA_VERSION = "approved-golden-case-v1"
SEMANTIC_VERDICTS = {"pass", "gap", "accepted_variance"}
ATTRIBUTIONS = {
    "none",
    "prompt_or_answer_composition",
    "rag_or_retrieval",
    "tool_or_data",
    "tool_behavior",
    "data_behavior",
    "guardrail_or_policy",
    "runtime_or_transport",
    "product_behavior",
    "evaluator_behavior",
}
BALLOT_DYNAMIC_FACT_RULES = set(BALLOT_DYNAMIC_CONTEXT_FIELDS)
_BALLOT_DYNAMIC_FIELD_TERMS = {
    "accrual_display_location": [
        "accrual_display_location", "accrual display location", "累积展示位置", "展示位置", "累积明细"
    ],
    "airdrop_token": ["airdrop_token", "airdrop token", "空投代币"],
    "concentration_note": [
        "concentration_note", "concentration note", "vote concentration", "voting concentration", "集中度提示", "投票集中"
    ],
    "early_redeem_rule": ["early_redeem_rule", "early redeem rule", "提前赎回规则"],
    "execution_rule": ["execution_rule", "execution rule", "执行规则", "执行机制"],
    "fixed_apy": ["fixed_apy", "fixed apy", "固定 apy", "固定收益率"],
    "gov_reward_detail": [
        "gov_reward_detail", "gov reward detail", "governance reward detail", "治理奖励细节", "奖励详情"
    ],
    "governance_rewards_rule": [
        "governance_rewards_rule", "governance rewards rule", "治理奖励规则"
    ],
    "proposal_creation_rule": [
        "proposal_creation_rule", "proposal creation rule", "提案发起规则", "提案创建规则"
    ],
    "proposal_display_location": [
        "proposal_display_location", "proposal display location", "提案展示位置", "提案页面"
    ],
    "proposal_threshold": ["proposal_threshold", "proposal threshold", "提案门槛"],
    "redeem_during_vote_rule": [
        "redeem_during_vote_rule", "redeem during vote rule", "投票期间赎回规则"
    ],
    "reward_source_summary": [
        "reward_source_summary", "reward source summary", "奖励来源摘要", "奖励来源"
    ],
    "snapshot_timing_rule": [
        "snapshot_timing_rule", "snapshot timing rule", "快照时间规则", "快照的具体时间规则", "快照的具体时机规则", "快照时点"
    ],
    "vote_change_rule": ["vote_change_rule", "vote change rule", "投票修改规则"],
    "vote_cost_note": ["vote_cost_note", "vote cost note", "投票费用", "gas"],
    "voting_power_rule": [
        "voting_power_rule", "voting power rule", "投票权计算规则", "投票权换算规则"
    ],
    "yield_denomination": [
        "yield_denomination", "yield denomination", "收益计价币种", "收益代币"
    ],
}
DYNAMIC_FACT_RULES = BALLOT_DYNAMIC_FACT_RULES | {
    "current_agent_redemption_policy",
    "current_agent_fee_schedule",
}
_FEE_TYPE_TERMS = {
    "mint_fee": ["mint fee", "mint_fee", "铸造费"],
    "redeem_fee": ["redeem fee", "redeem_fee", "赎回费"],
    "management_fee": ["management fee", "management_fee", "管理费"],
    "profit_share": ["profit share", "profit_share", "收益分成"],
}
_UNSUPPORTED_FEE_MECHANICS = [
    "annualized",
    "annually",
    "per annum",
    "per year",
    "年化",
    "按年",
    "deducted from your holdings",
    "从持仓中扣除",
    "no other fee types are currently configured",
    "only fee currently configured",
    "no profit share is configured",
    "未设置 profit share",
    "未设置收益分成",
    "不会对盈利额外抽成",
]
_UNSUPPORTED_SETTLEMENT_MECHANICS = [
    "settles positions",
    "close out your portion",
    "close positions as needed",
    "平仓结算",
]
_REAL_SECRET_PATTERNS = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.I),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
_REAL_EVM_ADDRESS = re.compile(r"\b0x(?!Eval)[a-fA-F0-9]{40}\b")


def normalize_approved_cases(
    source_rows: Iterable[dict[str, Any]],
    *,
    approved_by: str,
    source_version: str,
    existing_rows: Iterable[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Normalize product-owner-approved Q&A rows into evaluator fixtures."""
    approved_by = str(approved_by or "").strip()
    source_version = str(source_version or "").strip()
    if not approved_by:
        raise ValueError("approved_by is required")
    if not source_version:
        raise ValueError("source_version is required")

    merged: dict[str, dict[str, Any]] = {}
    for row in existing_rows:
        canonical = dict(row)
        _validate_approved_case(canonical)
        merged[str(canonical["id"])] = canonical

    for index, raw in enumerate(source_rows, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"source row {index} must be an object")
        canonical = _normalize_source_row(
            raw,
            approved_by=approved_by,
            source_version=source_version,
            index=index,
        )
        case_id = str(canonical["id"])
        previous = merged.get(case_id)
        if previous is not None:
            if _case_content(previous) != _case_content(canonical):
                raise ValueError(f"conflicting duplicate id: {case_id}")
            continue
        merged[case_id] = canonical
    output = [merged[case_id] for case_id in sorted(merged)]
    errors = validate_cases(output, min_cases=1)
    if errors:
        raise ValueError("invalid approved cases:\n" + "\n".join(errors))
    return output


def load_approved_cases(path: Path) -> list[dict[str, Any]]:
    """Load a normalized approved-case JSONL file."""
    rows = _read_rows(path)
    for row in rows:
        _validate_approved_case(row)
    errors = validate_cases(rows, min_cases=1)
    if errors:
        raise ValueError("invalid approved cases:\n" + "\n".join(errors))
    return rows


def write_jsonl(rows: Iterable[dict[str, Any]], path: Path) -> None:
    """Write stable UTF-8 JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for row in rows
    )
    path.write_text(payload + ("\n" if payload else ""), encoding="utf-8")


def build_preflight_contract(
    cases: list[dict[str, Any]],
    *,
    target_truth: dict[str, Any] | None,
) -> dict[str, Any]:
    """Freeze case scope and sanitized current truth before any live replay."""
    for case in cases:
        _validate_approved_case(case)
    truth = _validated_target_truth(target_truth)
    target_agent_type = str((truth or {}).get("agent_type") or "").casefold()
    dynamic_facts = dict((truth or {}).get("dynamic_facts") or {})
    blockers: list[str] = []
    matrix: list[dict[str, Any]] = []
    target_type_required = False
    dynamic_truth_required = False
    for case in cases:
        applicable_types = sorted(
            {str(value).casefold() for value in case.get("applicable_agent_types", [])}
        )
        if applicable_types:
            target_type_required = True
        applicable = not applicable_types or (
            bool(target_agent_type) and target_agent_type in applicable_types
        )
        rules = [str(value) for value in case.get("dynamic_fact_rules", [])]
        if rules and (applicable or not target_agent_type):
            dynamic_truth_required = True
        availability: dict[str, str] = {}
        for rule in rules:
            fact = dynamic_facts.get(rule)
            if not isinstance(fact, dict):
                availability[rule] = "missing"
            else:
                availability[rule] = str(fact.get("availability") or "available")
        matrix.append(
            {
                "case_id": str(case["id"]),
                "applicable": applicable,
                "applicable_agent_types": applicable_types,
                "static_fact_group_count": len(_fact_groups(case)),
                "dynamic_fact_variables": [
                    str(value) for value in case.get("dynamic_fact_variables", [])
                ],
                "dynamic_fact_rules": rules,
                "dynamic_fact_availability": availability,
            }
        )
    if target_type_required and not target_agent_type:
        blockers.append("target agent type missing")
    if dynamic_truth_required and not truth:
        blockers.append("dynamic target truth missing")
    missing_rules = sorted(
        {
            rule
            for row in matrix
            if row["applicable"]
            for rule, availability in row["dynamic_fact_availability"].items()
            if availability == "missing"
        }
    )
    if missing_rules:
        blockers.append(f"dynamic target truth missing for {missing_rules}")
    return {
        "schema_version": "approved-golden-preflight-v1",
        "status": "ready" if not blockers else "blocked",
        "live_run_allowed": not blockers,
        "case_contract_sha256": _contract_digest(cases),
        "target_truth_sha256": _contract_digest(truth) if truth else None,
        "target_agent_type": target_agent_type or None,
        "case_ids": [row["case_id"] for row in matrix if row["applicable"]],
        "blockers": blockers,
        "fact_matrix": matrix,
    }


def validate_live_preflight(
    preflight: dict[str, Any],
    cases: list[dict[str, Any]],
    *,
    target_truth: dict[str, Any] | None = None,
    require_target_truth: bool = False,
) -> None:
    """Reject approved live replay when its frozen case contract is stale."""
    if preflight.get("status") != "ready" or preflight.get("live_run_allowed") is not True:
        raise ValueError("approved Golden preflight is not ready")
    if preflight.get("case_contract_sha256") != _contract_digest(cases):
        raise ValueError("approved Golden case contract changed after preflight")
    expected_ids = sorted(str(case["id"]) for case in cases)
    matrix_ids = sorted(
        str(row.get("case_id"))
        for row in preflight.get("fact_matrix", [])
        if isinstance(row, dict)
    )
    if matrix_ids != expected_ids:
        raise ValueError("approved Golden preflight case matrix is incomplete")
    expected_truth_hash = preflight.get("target_truth_sha256")
    if require_target_truth and expected_truth_hash:
        if target_truth is None:
            raise ValueError("approved Golden live replay requires frozen target truth")
        truth = _validated_target_truth(target_truth)
        if _contract_digest(truth) != expected_truth_hash:
            raise ValueError("approved Golden target truth changed after preflight")


def build_target_truth_from_marketplace_context(
    marketplace_context: dict[str, Any],
) -> dict[str, Any]:
    """Build sanitized evaluator truth from the typed Marketplace AI context."""
    if not isinstance(marketplace_context, dict):
        raise ValueError("Marketplace context must be an object")
    payload = marketplace_context
    if isinstance(marketplace_context.get("data"), dict):
        payload = marketplace_context["data"]
    agent = payload.get("agent")
    if not isinstance(agent, dict):
        raise ValueError("Marketplace context agent is required")
    agent_type = str(agent.get("agent_type") or "").strip().casefold()
    if not agent_type:
        raise ValueError("Marketplace context agent.agent_type is required")
    dynamic_facts = {
        "current_agent_redemption_policy": _redemption_target_fact(
            payload.get("redemption_policy")
        ),
        "current_agent_fee_schedule": _fee_target_fact(
            payload.get("fee_schedule")
        ),
    }
    dynamic_facts.update(_ballot_target_facts(payload, agent_type=agent_type))
    return {
        "agent_type": agent_type,
        "dynamic_facts": dynamic_facts,
    }


def _ballot_target_facts(
    payload: dict[str, Any], *, agent_type: str
) -> dict[str, dict[str, Any]]:
    if agent_type != "ballot":
        return {}
    agent = payload["agent"]
    facts: dict[str, dict[str, Any]] = {}
    direct_values = {
        "project_name": agent.get("name"),
        "project_token": agent.get("accept_token_symbol"),
    }
    for rule in sorted(BALLOT_DYNAMIC_FACT_RULES):
        value = direct_values.get(rule)
        if value is not None and str(value).strip():
            facts[rule] = {
                "required_fact_groups": [[str(value).strip()]],
                "forbidden_claims": [],
                "availability": "available",
                "source": f"agent.{('name' if rule == 'project_name' else 'accept_token_symbol')}",
            }
        else:
            facts[rule] = {
                "required_fact_groups": [
                    _BALLOT_DYNAMIC_FIELD_TERMS.get(
                        rule, [rule, rule.replace("_", " ")]
                    ),
                    ["not provided", "unavailable", "not returned", "未提供", "无法获取"]
                ],
                "forbidden_claims": [],
                "availability": "not_provided",
                "source": "marketplace_agent_context",
            }
    return facts


def _redemption_target_fact(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Marketplace context redemption_policy is required")
    available = value.get("available")
    status = str(value.get("status") or "").strip().casefold()
    if available is True and status == "ok":
        seconds = _bounded_integer(
            value.get("lock_period_seconds"),
            field="redemption_policy.lock_period_seconds",
        )
        claim_required = _required_boolean(
            value.get("claim_required"),
            field="redemption_policy.claim_required",
        )
        settlement_required = _required_boolean(
            value.get("settlement_required"),
            field="redemption_policy.settlement_required",
        )
        groups = [_lock_period_terms(seconds)]
        groups.append(
            ["claim", "领取", "申领"]
            if claim_required
            else ["no separate claim", "无需另行领取", "无需申领"]
        )
        groups.append(
            ["settlement", "结算"]
            if settlement_required
            else ["no settlement wait", "无需等待结算"]
        )
        forbidden = list(_UNSUPPORTED_SETTLEMENT_MECHANICS)
        forbidden.extend(
            ["no lock-up", "no lockup", "没有锁定期", "无锁定期"]
            if seconds > 0
            else []
        )
        return {
            "required_fact_groups": groups,
            "forbidden_claims": forbidden,
        }
    if available is False and status in {"unsupported", "unavailable"}:
        terms = (
            ["unsupported", "不支持", "未提供"]
            if status == "unsupported"
            else ["unavailable", "暂不可用", "无法获取"]
        )
        return {"required_fact_groups": [terms], "forbidden_claims": []}
    raise ValueError("Marketplace redemption_policy has inconsistent availability/status")


def _fee_target_fact(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Marketplace context fee_schedule is required")
    available = value.get("available")
    status = str(value.get("status") or "").strip().casefold()
    if available is True and status == "ok":
        raw_fees = value.get("fees")
        if not isinstance(raw_fees, list) or not raw_fees:
            raise ValueError("Marketplace fee_schedule.fees must be non-empty when available")
        groups: list[list[str]] = []
        seen_types: set[str] = set()
        for index, fee in enumerate(raw_fees):
            if not isinstance(fee, dict):
                raise ValueError(f"Marketplace fee_schedule.fees[{index}] must be an object")
            fee_type = str(fee.get("fee_type") or "").strip().casefold()
            if fee_type not in _FEE_TYPE_TERMS:
                raise ValueError(f"Marketplace fee_schedule has unsupported fee_type {fee_type!r}")
            if fee_type in seen_types:
                raise ValueError(f"Marketplace fee_schedule repeats fee_type {fee_type!r}")
            seen_types.add(fee_type)
            bps = _bounded_integer(
                fee.get("rate_bps"),
                field=f"fee_schedule.fees[{index}].rate_bps",
                maximum=10000,
            )
            groups.append(list(_FEE_TYPE_TERMS[fee_type]))
            groups.append(_rate_terms(bps))
        return {
            "required_fact_groups": groups,
            "forbidden_claims": list(_UNSUPPORTED_FEE_MECHANICS),
        }
    if available is False and status in {"unsupported", "unavailable"}:
        terms = (
            ["unsupported", "不支持", "未提供"]
            if status == "unsupported"
            else ["unavailable", "暂不可用", "无法获取"]
        )
        return {"required_fact_groups": [terms], "forbidden_claims": []}
    raise ValueError("Marketplace fee_schedule has inconsistent availability/status")


def _lock_period_terms(seconds: int) -> list[str]:
    if seconds == 0:
        return ["0 seconds", "0 秒", "no lock-up", "没有锁定期"]
    hours, remainder = divmod(seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    return [
        f"{seconds} seconds",
        f"{seconds:,} seconds",
        f"{seconds} 秒",
        f"{seconds:,} 秒",
        f"{hours}h {minutes}m {remaining_seconds}s",
        f"{hours} hours {minutes} minutes {remaining_seconds} seconds",
        f"{hours} hours, {minutes} minutes, and {remaining_seconds} seconds",
        f"{hours} 小时 {minutes} 分 {remaining_seconds} 秒",
        f"{hours}小时{minutes}分{remaining_seconds}秒",
        f"{hours}小时{minutes}分钟{remaining_seconds}秒",
    ]


def _rate_terms(bps: int) -> list[str]:
    whole, fraction = divmod(bps, 100)
    percent = f"{whole}.{fraction:02d}".rstrip("0").rstrip(".")
    terms = [
        f"{bps} bps",
        f"{bps} basis points",
        f"{percent}%",
        f"{percent} percent",
    ]
    if fraction == 0:
        terms.append(f"{whole}.0%")
    return terms


def _bounded_integer(value: Any, *, field: str, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Marketplace {field} must be a non-negative integer")
    if maximum is not None and value > maximum:
        raise ValueError(f"Marketplace {field} must not exceed {maximum}")
    return value


def _required_boolean(value: Any, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"Marketplace {field} must be a boolean")
    return value


def build_optimization_report(
    cases: list[dict[str, Any]],
    baseline_report: dict[str, Any],
    *,
    semantic_reviews: Iterable[dict[str, Any]] | None = None,
    target_truth: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Join live answers with hard checks and optional advisory semantic reviews."""
    for case in cases:
        _validate_approved_case(case)
    baseline_by_id = {
        str(row.get("case_id")): row
        for row in baseline_report.get("results", [])
        if isinstance(row, dict) and row.get("case_id")
    }
    review_by_id = _semantic_review_map(semantic_reviews or ())
    unknown_reviews = sorted(set(review_by_id) - {str(case["id"]) for case in cases})
    if unknown_reviews:
        raise ValueError(f"semantic reviews contain unknown case ids: {unknown_reviews}")

    target_truth = _validated_target_truth(target_truth)
    target_agent_type = str((target_truth or {}).get("agent_type") or "").casefold()
    dynamic_facts = dict((target_truth or {}).get("dynamic_facts") or {})
    results: list[dict[str, Any]] = []
    release_blockers: list[str] = []
    completion_blockers: list[str] = []
    review_packet: list[dict[str, Any]] = []
    active_cases: list[dict[str, Any]] = []
    not_applicable_count = 0
    for case in cases:
        case_id = str(case["id"])
        applicable_types = {
            str(value).casefold() for value in case.get("applicable_agent_types", [])
        }
        if applicable_types and target_agent_type and target_agent_type not in applicable_types:
            not_applicable_count += 1
            results.append(
                {
                    "case_id": case_id,
                    "area": case["area"],
                    "risk_level": str(case.get("risk_level") or "low"),
                    "status": "not_applicable",
                    "hard_pass": True,
                    "transport_ok": None,
                    "missing_fact_groups": [],
                    "missing_static_fact_groups": [],
                    "missing_dynamic_fact_groups": [],
                    "missing_dynamic_rules": [],
                    "forbidden_hits": [],
                    "semantic_verdict": "not_applicable",
                    "semantic_reason": None,
                    "semantic_gaps": [],
                    "dimension_scores": {},
                    "suggested_attribution": "none",
                    "answer": "",
                }
            )
            continue
        active_cases.append(case)
        target_agent_type_missing = bool(applicable_types and not target_agent_type)
        baseline = baseline_by_id.get(case_id)
        answer = str((baseline or {}).get("content") or "")
        transport_ok = bool(
            baseline
            and baseline.get("status") == "completed"
            and answer.strip()
        )
        static_required_groups = _fact_groups(case)
        dynamic_required_groups: list[list[str]] = []
        dynamic_rules = [str(rule) for rule in case.get("dynamic_fact_rules", [])]
        missing_dynamic_rules = [
            rule for rule in dynamic_rules if rule not in dynamic_facts
        ]
        dynamic_forbidden: list[str] = []
        for rule in dynamic_rules:
            fact = dynamic_facts.get(rule)
            if not isinstance(fact, dict):
                continue
            dynamic_required_groups.extend(
                _validated_fact_groups(
                    fact.get("required_fact_groups"), index=f"target truth {rule}"
                )
            )
            dynamic_forbidden.extend(
                _string_list(
                    fact.get("forbidden_claims", []),
                    "forbidden_claims",
                    f"target truth {rule}",
                )
            )
        missing_static_groups = (
            [
                group
                for group in static_required_groups
                if not _group_matches(group, answer)
            ]
            if transport_ok
            else static_required_groups
        )
        missing_dynamic_groups = (
            [
                group
                for group in dynamic_required_groups
                if not _group_matches(group, answer)
            ]
            if transport_ok
            else dynamic_required_groups
        )
        missing_groups = missing_static_groups + missing_dynamic_groups
        forbidden = _forbidden_claims(case) + dynamic_forbidden
        forbidden_hits = [
            claim for claim in forbidden if _contains_forbidden_claim(answer, claim)
        ]
        hard_pass = (
            transport_ok
            and not missing_groups
            and not missing_dynamic_rules
            and not target_agent_type_missing
            and not forbidden_hits
        )
        review = review_by_id.get(case_id)
        semantic_verdict = str((review or {}).get("verdict") or "pending")
        attribution = _suggest_attribution(
            case,
            transport_ok=transport_ok,
            tool_calls=[str(value) for value in (baseline or {}).get("tool_calls", [])],
            missing_static_groups=missing_static_groups,
            missing_dynamic_groups=missing_dynamic_groups,
            forbidden_hits=forbidden_hits,
            semantic_review=review,
        )
        if missing_dynamic_rules:
            attribution = "data_behavior"

        if not transport_ok:
            release_blockers.append(f"{case_id}: live baseline missing or failed")
        if target_agent_type_missing:
            release_blockers.append(f"{case_id}: target agent type missing")
        if missing_dynamic_rules:
            release_blockers.append(
                f"{case_id}: dynamic target truth missing for {missing_dynamic_rules}"
            )
        elif missing_groups:
            release_blockers.append(f"{case_id}: required facts missing")
        if forbidden_hits:
            release_blockers.append(f"{case_id}: forbidden claims present")

        risk_level = str(case.get("risk_level") or "low")
        if review and semantic_verdict == "gap" and risk_level in {"high", "critical"}:
            completion_blockers.append(f"{case_id}: high-risk semantic gap")

        if not hard_pass:
            case_status = "blocked"
        elif semantic_verdict == "pending":
            case_status = "needs_semantic_review"
        elif semantic_verdict == "gap":
            case_status = "needs_optimization"
        else:
            case_status = "passed"

        case_result = {
            "case_id": case_id,
            "area": case["area"],
            "risk_level": risk_level,
            "status": case_status,
            "hard_pass": hard_pass,
            "transport_ok": transport_ok,
            "missing_fact_groups": missing_groups,
            "missing_static_fact_groups": missing_static_groups,
            "missing_dynamic_fact_groups": missing_dynamic_groups,
            "missing_dynamic_rules": missing_dynamic_rules,
            "target_agent_type_missing": target_agent_type_missing,
            "forbidden_hits": forbidden_hits,
            "semantic_verdict": semantic_verdict,
            "semantic_reason": (review or {}).get("reason"),
            "semantic_gaps": list((review or {}).get("gaps") or []),
            "dimension_scores": dict((review or {}).get("dimension_scores") or {}),
            "suggested_attribution": attribution,
            "answer": answer,
        }
        results.append(case_result)
        if semantic_verdict == "pending" and hard_pass:
            review_packet.append(
                _semantic_review_item(
                    case,
                    answer,
                    target_truth={
                        rule: dynamic_facts[rule]
                        for rule in dynamic_rules
                        if rule in dynamic_facts
                    },
                )
            )

    active_results = [item for item in results if item["status"] != "not_applicable"]
    hard_failure_count = sum(not item["hard_pass"] for item in active_results)
    semantic_pending_count = sum(
        item["semantic_verdict"] == "pending" for item in active_results
    )
    semantic_gap_count = sum(
        item["semantic_verdict"] == "gap" for item in active_results
    )
    if release_blockers:
        status = "blocked"
    elif semantic_gap_count:
        status = "needs_optimization"
    elif semantic_pending_count:
        status = "needs_semantic_review"
    else:
        status = "passed"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "baseline_suite_id": baseline_report.get("suite_id"),
        "summary": {
            "case_count": len(active_results),
            "not_applicable_count": not_applicable_count,
            "hard_failure_count": hard_failure_count,
            "semantic_pending_count": semantic_pending_count,
            "semantic_gap_count": semantic_gap_count,
            "semantic_pass_or_accepted_count": sum(
                item["semantic_verdict"] in {"pass", "accepted_variance"}
                for item in active_results
            ),
        },
        "coverage": _coverage_summary(active_cases),
        "release_blockers": release_blockers,
        "completion_blockers": completion_blockers,
        "case_results": results,
        "attribution_summary": _attribution_summary(results),
        "repair_batches": _repair_batches(results),
        "semantic_review_packet": review_packet,
    }


def build_iteration_decision(
    report: dict[str, Any],
    *,
    previous_reports: Iterable[dict[str, Any]],
    max_same_failure_rounds: int = 2,
) -> dict[str, Any]:
    """Stop live patch loops when the same failure batch survives twice."""
    if max_same_failure_rounds < 1:
        raise ValueError("max_same_failure_rounds must be positive")
    if report.get("status") == "passed":
        return {
            "schema_version": "approved-golden-iteration-v1",
            "decision": "closeout",
            "rerun_budget_exhausted": False,
            "same_failure_rounds": 0,
            "failure_signature": None,
        }
    if (
        int((report.get("summary") or {}).get("semantic_pending_count", 0)) > 0
        and not report.get("repair_batches")
    ):
        return {
            "schema_version": "approved-golden-iteration-v1",
            "decision": "complete_semantic_review",
            "rerun_budget_exhausted": False,
            "same_failure_rounds": 0,
            "failure_signature": None,
        }
    signature = _failure_signature(report)
    same_rounds = 1
    for previous in reversed(list(previous_reports)):
        if _failure_signature(previous) != signature:
            break
        same_rounds += 1
    exhausted = same_rounds >= max_same_failure_rounds
    return {
        "schema_version": "approved-golden-iteration-v1",
        "decision": "stop_and_redesign" if exhausted else "fix_batches",
        "rerun_budget_exhausted": exhausted,
        "same_failure_rounds": same_rounds,
        "failure_signature": signature,
        "repair_batches": list(report.get("repair_batches") or []),
    }


def build_closeout_report(
    cases: list[dict[str, Any]],
    preflight: dict[str, Any],
    baseline_report: dict[str, Any],
    optimization_report: dict[str, Any],
) -> dict[str, Any]:
    """Require one complete, unspliced live suite for final acceptance."""
    validate_live_preflight(preflight, cases)
    suite_id = str(baseline_report.get("suite_id") or "")
    if baseline_report.get("suite_mode") != "full_suite" or not suite_id:
        raise ValueError("closeout requires one full_suite live replay")
    results = [
        row for row in baseline_report.get("results", []) if isinstance(row, dict)
    ]
    if any(str(row.get("suite_id") or "") != suite_id for row in results):
        raise ValueError("mixed suite evidence cannot be used for closeout")
    expected_ids = sorted(str(value) for value in preflight.get("case_ids", []))
    actual_ids = sorted(str(row.get("case_id") or "") for row in results)
    if actual_ids != expected_ids or len(actual_ids) != len(set(actual_ids)):
        raise ValueError("full_suite results do not match the frozen applicable cases")
    if baseline_report.get("status") != "passed" or any(
        row.get("status") != "completed" for row in results
    ):
        raise ValueError("full_suite live replay is not complete")
    if optimization_report.get("baseline_suite_id") != suite_id:
        raise ValueError("optimization report does not reference the full suite")
    summary = dict(optimization_report.get("summary") or {})
    zero_fields = (
        "hard_failure_count",
        "semantic_pending_count",
        "semantic_gap_count",
    )
    if (
        optimization_report.get("status") != "passed"
        or any(int(summary.get(field, -1)) != 0 for field in zero_fields)
        or optimization_report.get("release_blockers")
        or optimization_report.get("completion_blockers")
    ):
        raise ValueError("optimization report is not ready for closeout")
    return {
        "schema_version": "approved-golden-closeout-v1",
        "status": "passed",
        "single_shot_full_suite": True,
        "suite_id": suite_id,
        "case_contract_sha256": preflight["case_contract_sha256"],
        "target_truth_sha256": preflight.get("target_truth_sha256"),
        "summary": summary,
        "release_blockers": [],
        "completion_blockers": [],
    }


def _normalize_source_row(
    raw: dict[str, Any],
    *,
    approved_by: str,
    source_version: str,
    index: int,
) -> dict[str, Any]:
    question = str(raw.get("question") or raw.get("user_message") or "").strip()
    ideal_answer = str(raw.get("ideal_answer") or "").strip()
    if not question:
        raise ValueError(f"source row {index}: question is required")
    if not ideal_answer:
        raise ValueError(f"source row {index}: ideal_answer is required")
    _reject_sensitive_values(raw, index=index)

    groups = _validated_fact_groups(raw.get("required_fact_groups"), index=index)
    case_id = str(raw.get("id") or "").strip() or _stable_case_id(question)
    action = str(raw.get("expected_input_action") or "allow")
    if action == "refuse" and not str(raw.get("expected_input_category") or "").strip():
        raise ValueError(
            f"source row {index}: expected_input_category is required for refusal cases"
        )
    category = str(
        raw.get("expected_input_category")
        or "allowed"
    )
    forbidden = _string_list(raw.get("forbidden_claims", []), "forbidden_claims", index)
    tags = _string_list(raw.get("tags", []), "tags", index)
    area = str(raw.get("area") or "incremental_product_case").strip()
    locale = str(raw.get("locale") or _infer_locale(question)).strip()
    canonical: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "id": case_id,
        "locale": locale,
        "area": area,
        "user_message": question,
        "ideal_answer": ideal_answer,
        "expected_input_action": action,
        "expected_input_category": category,
        "requires_rag": bool(raw.get("requires_rag", False)),
        "requires_tool": raw.get("requires_tool"),
        "required_fact_groups": groups,
        "risk_level": str(raw.get("risk_level") or "low"),
        "quality_axes": _string_list(
            raw.get("quality_axes", ["correctness", "completeness"]),
            "quality_axes",
            index,
        ),
        "tags": sorted(set(tags + ["approved_golden_case"])),
        "approval": {
            "status": "approved",
            "approved_by": approved_by,
            "source_version": source_version,
        },
    }
    if "source_question_id" in raw:
        source_question_id = str(raw["source_question_id"] or "").strip()
        if not source_question_id:
            raise ValueError(f"source row {index}: source_question_id must be non-empty")
        canonical["source_question_id"] = source_question_id
    if "applicable_agent_types" in raw:
        canonical["applicable_agent_types"] = sorted(
            {
                value.casefold()
                for value in _string_list(
                    raw["applicable_agent_types"], "applicable_agent_types", index
                )
            }
        )
    for field in (
        "dynamic_fact_variables",
        "dynamic_fact_rules",
        "expected_sources",
        "expected_fields",
        "expected_tool_events",
    ):
        if field in raw:
            canonical[field] = _string_list(raw[field], field, index)
    if "requires_wallet" in raw:
        canonical["requires_wallet"] = bool(raw["requires_wallet"])
    if "fixture_proxy_payload" in raw:
        canonical["fixture_proxy_payload"] = raw["fixture_proxy_payload"]
    if action == "refuse":
        canonical["safe_response_contains"] = [group[0] for group in groups]
        canonical["safe_response_forbids"] = forbidden
    else:
        canonical["answer_traits"] = [group[0] for group in groups]
        canonical["forbidden_claims"] = forbidden
    _validate_approved_case(canonical)
    return canonical


def _validate_approved_case(row: dict[str, Any]) -> None:
    case_id = str(row.get("id") or "<unknown>")
    if row.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{case_id}: unsupported approved case schema")
    approval = row.get("approval")
    if not isinstance(approval, dict) or approval.get("status") != "approved":
        raise ValueError(f"{case_id}: case must be product-owner approved")
    if not str(approval.get("approved_by") or "").strip():
        raise ValueError(f"{case_id}: approval.approved_by is required")
    if not str(approval.get("source_version") or "").strip():
        raise ValueError(f"{case_id}: approval.source_version is required")
    if not str(row.get("ideal_answer") or "").strip():
        raise ValueError(f"{case_id}: ideal_answer is required")
    _validated_fact_groups(row.get("required_fact_groups"), index=case_id)
    _string_list(
        row.get("dynamic_fact_variables", []), "dynamic_fact_variables", case_id
    )
    dynamic_rules = _string_list(
        row.get("dynamic_fact_rules", []), "dynamic_fact_rules", case_id
    )
    unknown_rules = sorted(set(dynamic_rules) - DYNAMIC_FACT_RULES)
    if unknown_rules:
        raise ValueError(f"{case_id}: unsupported dynamic fact rules {unknown_rules}")
    for agent_type in _string_list(
        row.get("applicable_agent_types", []), "applicable_agent_types", case_id
    ):
        if agent_type != agent_type.casefold():
            raise ValueError(f"{case_id}: applicable_agent_types must be lowercase")
    _reject_sensitive_values(row, index=case_id)


def _validated_target_truth(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("target truth must be an object")
    _reject_sensitive_values(value, index="target truth")
    agent_type = str(value.get("agent_type") or "").strip().casefold()
    if not agent_type:
        raise ValueError("target truth agent_type is required")
    raw_facts = value.get("dynamic_facts", {})
    if not isinstance(raw_facts, dict):
        raise ValueError("target truth dynamic_facts must be an object")
    unknown_rules = sorted(set(raw_facts) - DYNAMIC_FACT_RULES)
    if unknown_rules:
        raise ValueError(f"target truth has unsupported dynamic facts {unknown_rules}")
    facts: dict[str, Any] = {}
    for rule, fact in raw_facts.items():
        if not isinstance(fact, dict):
            raise ValueError(f"target truth {rule} must be an object")
        facts[rule] = {
            "required_fact_groups": _validated_fact_groups(
                fact.get("required_fact_groups"), index=f"target truth {rule}"
            ),
            "forbidden_claims": _string_list(
                fact.get("forbidden_claims", []),
                "forbidden_claims",
                f"target truth {rule}",
            ),
        }
        for field in ("availability", "source"):
            if field in fact:
                value_text = str(fact[field] or "").strip()
                if not value_text:
                    raise ValueError(f"target truth {rule}.{field} must be non-empty")
                facts[rule][field] = value_text
    return {"agent_type": agent_type, "dynamic_facts": facts}


def _validated_fact_groups(value: Any, *, index: Any) -> list[list[str]]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"source row {index}: required_fact_groups must be non-empty")
    groups: list[list[str]] = []
    for group in value:
        if not isinstance(group, list) or not group:
            raise ValueError(
                f"source row {index}: required_fact_groups entries must be non-empty lists"
            )
        normalized = [str(item).strip() for item in group]
        if any(not item for item in normalized):
            raise ValueError(
                f"source row {index}: required_fact_groups alternatives must be non-empty"
            )
        groups.append(normalized)
    return groups


def _string_list(value: Any, field: str, index: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"source row {index}: {field} must be a list")
    output = [str(item).strip() for item in value]
    if any(not item for item in output):
        raise ValueError(f"source row {index}: {field} contains an empty value")
    return output


def _semantic_review_map(
    reviews: Iterable[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for index, review in enumerate(reviews, start=1):
        if not isinstance(review, dict):
            raise ValueError(f"semantic review {index} must be an object")
        case_id = str(review.get("case_id") or "").strip()
        verdict = str(review.get("verdict") or "").strip()
        attribution = str(review.get("attribution") or "").strip()
        if not case_id:
            raise ValueError(f"semantic review {index}: case_id is required")
        if verdict not in SEMANTIC_VERDICTS:
            raise ValueError(f"{case_id}: invalid semantic verdict {verdict!r}")
        if attribution not in ATTRIBUTIONS:
            raise ValueError(f"{case_id}: invalid attribution {attribution!r}")
        if not str(review.get("reason") or "").strip():
            raise ValueError(f"{case_id}: semantic review reason is required")
        gaps = review.get("gaps")
        if not isinstance(gaps, list) or any(
            not isinstance(gap, str) or not gap.strip() for gap in gaps
        ):
            raise ValueError(f"{case_id}: semantic review gaps must be a string list")
        scores = review.get("dimension_scores")
        if not isinstance(scores, dict) or any(
            not isinstance(score, int) or score not in {0, 1, 2}
            for score in scores.values()
        ):
            raise ValueError(
                f"{case_id}: semantic review dimension scores must be 0, 1, or 2"
            )
        if case_id in output:
            raise ValueError(f"duplicate semantic review: {case_id}")
        output[case_id] = review
    return output


def _semantic_review_item(
    case: dict[str, Any],
    answer: str,
    *,
    target_truth: dict[str, Any],
) -> dict[str, Any]:
    dynamic_rules = [str(rule) for rule in case.get("dynamic_fact_rules", [])]
    return {
        "case_id": case["id"],
        "judge_mode": "llm_judge_advisory",
        "question": case["user_message"],
        "ideal_answer": case["ideal_answer"],
        "actual_answer": answer,
        "risk_level": case.get("risk_level", "low"),
        "quality_axes": case.get("quality_axes", []),
        "dynamic_fact_rules": dynamic_rules,
        "target_truth": target_truth,
        "instruction": (
            "Judge semantic equivalence, factual completeness, and boundary safety. "
            "Do not require matching wording. For dynamic fact rules, the supplied "
            "current-Agent target truth overrides the static ideal answer. Return one "
            "JSON object using the output schema."
        ),
        "output_schema": {
            "case_id": case["id"],
            "verdict": "pass | gap | accepted_variance",
            "reason": "non-empty string",
            "gaps": ["string"],
            "attribution": sorted(ATTRIBUTIONS),
            "dimension_scores": {"quality_axis": "0 | 1 | 2"},
        },
    }


def _coverage_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mode": "informational_incremental",
        "areas": dict(sorted(Counter(str(case["area"]) for case in cases).items())),
        "risk_levels": dict(
            sorted(Counter(str(case.get("risk_level") or "low") for case in cases).items())
        ),
        "tags": dict(
            sorted(
                Counter(
                    str(tag)
                    for case in cases
                    for tag in case.get("tags", [])
                ).items()
            )
        ),
    }


def _failure_modes(result: dict[str, Any]) -> list[str]:
    modes: list[str] = []
    if result.get("transport_ok") is False:
        modes.append("runtime_or_transport")
    if result.get("target_agent_type_missing"):
        modes.append("target_agent_type_missing")
    if result.get("missing_dynamic_rules"):
        modes.append("dynamic_truth_missing")
    if result.get("missing_static_fact_groups"):
        modes.append("static_fact_missing")
    if result.get("missing_dynamic_fact_groups"):
        modes.append("dynamic_fact_missing")
    if result.get("forbidden_hits"):
        modes.append("forbidden_claim")
    if result.get("semantic_verdict") == "gap":
        modes.append("semantic_gap")
    return modes


def _attribution_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, dict[str, set[str]]] = {}
    for result in results:
        attribution = str(result.get("suggested_attribution") or "none")
        modes = _failure_modes(result)
        if attribution == "none" or not modes:
            continue
        bucket = grouped.setdefault(
            attribution, {"case_ids": set(), "failure_modes": set()}
        )
        bucket["case_ids"].add(str(result["case_id"]))
        bucket["failure_modes"].update(modes)
    return {
        attribution: {
            "case_count": len(values["case_ids"]),
            "case_ids": sorted(values["case_ids"]),
            "failure_modes": sorted(values["failure_modes"]),
        }
        for attribution, values in sorted(grouped.items())
    }


def _repair_batches(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary = _attribution_summary(results)
    result_by_id = {str(result["case_id"]): result for result in results}
    return [
        {
            "attribution": attribution,
            "case_ids": values["case_ids"],
            "failure_modes": values["failure_modes"],
            "runtime_retry_guard_allowed": bool(
                values["failure_modes"]
                and set(values["failure_modes"]) == {"forbidden_claim"}
                and all(
                    str(result_by_id[case_id].get("risk_level"))
                    in {"high", "critical"}
                    for case_id in values["case_ids"]
                )
            ),
        }
        for attribution, values in summary.items()
    ]


def _failure_signature(report: dict[str, Any]) -> str:
    batches = report.get("repair_batches") or []
    return _contract_digest(batches)


def _contract_digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _fact_groups(case: dict[str, Any]) -> list[list[str]]:
    return [[str(item) for item in group] for group in case["required_fact_groups"]]


def _forbidden_claims(case: dict[str, Any]) -> list[str]:
    values = case.get("forbidden_claims") or case.get("safe_response_forbids") or []
    return [str(item) for item in values]


def _case_content(case: dict[str, Any]) -> dict[str, Any]:
    """Compare business content while allowing approval batch metadata to advance."""
    return {key: value for key, value in case.items() if key != "approval"}


def _group_matches(group: list[str], answer: str) -> bool:
    return any(_contains(answer, alternative) for alternative in group)


def _contains(text: str, fragment: str) -> bool:
    return _normalize_text(fragment) in _normalize_text(text)


def _contains_forbidden_claim(text: str, fragment: str) -> bool:
    """Match forbidden claims without treating an explicit denial as an assertion."""
    fragment_tokens = re.findall(r"\w+", str(fragment).casefold())
    if not fragment_tokens:
        return False
    normalized_fragment = " ".join(fragment_tokens)
    if re.match(
        r"^(?:no|not|never|without|cannot|can t|does not|doesn t|do not|"
        r"did not|is not|are not|will not|won t)\b",
        normalized_fragment,
    ) or normalized_fragment.startswith(("不", "无", "没", "未")):
        return _contains(text, fragment)

    pattern = re.compile(r"[^\w]+".join(map(re.escape, fragment_tokens)), re.I)
    for match in pattern.finditer(str(text)):
        clause_prefix = re.split(r"[.!?;。！？；\n]", str(text)[: match.start()])[-1]
        nearby = clause_prefix[-96:]
        english_words = re.findall(r"[a-z]+", nearby.casefold())[-10:]
        english_prefix = " ".join(english_words)
        negated_en = bool(
            re.search(
                r"\b(?:no|not|never|without|cannot|can t|does not|doesn t|"
                r"do not|did not|is not|are not|will not|won t)\b",
                english_prefix,
            )
        )
        negated_zh = bool(re.search(r"(?:不|无|没有|不会|无法|并未)[^。！？；]{0,24}$", nearby))
        if not (negated_en or negated_zh):
            return True
    return False


def _normalize_text(value: str) -> str:
    normalized = str(value).casefold().replace("%", " percent ")
    for pattern in _MISSING_FACT_PATTERNS:
        normalized = pattern.sub(" missingfactmarker ", normalized)
    return " ".join(re.sub(r"[^\w]+", " ", normalized).split())


_MISSING_FACT_PATTERNS = (
    re.compile(
        r"\b(?:unavailable|not available|not provided|not disclosed|not returned|"
        r"not materialized|no data|cannot retrieve|can't retrieve|no disclosed|"
        r"unable to (?:retrieve|determine|provide))\b",
        re.I,
    ),
    re.compile(
        r"\bno\b[^.!?\n]{0,60}\b(?:available|provided|disclosed|returned|"
        r"to report|on record)\b",
        re.I,
    ),
    re.compile(
        r"\bno\s+(?:(?:current|open)\s+)?(?:positions?|holdings?|holders?|shares?|trades?|"
        r"reports?|activities|activity)\b",
        re.I,
    ),
    re.compile(r"未(?:提供|披露|返回|物化)|暂(?:无|不可用)|无法(?:获取|提供|确定|检索)"),
    re.compile(r"没有可(?:用|展示)"),
    re.compile(r"(?:没有|无)[^，。；！？\n]{0,16}(?:仓位|持仓|持有人|份额|交易|报告|活动|数据|记录)"),
    re.compile(r"(?:目前|当前)?没有任何(?:持有者|持有人|仓位|持仓|活动)"),
    re.compile(r"不存在\s*(?:top\s*holder|前列持有人|最大持有人)", re.I),
)


def _suggest_attribution(
    case: dict[str, Any],
    *,
    transport_ok: bool,
    tool_calls: list[str],
    missing_static_groups: list[list[str]],
    missing_dynamic_groups: list[list[str]],
    forbidden_hits: list[str],
    semantic_review: dict[str, Any] | None,
) -> str:
    if not transport_ok:
        return "runtime_or_transport"
    if forbidden_hits:
        return "guardrail_or_policy"
    if missing_dynamic_groups:
        required_tool = str(case.get("requires_tool") or "")
        if required_tool and required_tool not in tool_calls:
            return "tool_behavior"
        if case.get("expected_fields") and not required_tool:
            return "data_behavior"
        return "prompt_or_answer_composition"
    if missing_static_groups:
        if case.get("requires_rag") or case.get("expected_sources"):
            return "rag_or_retrieval"
        return "prompt_or_answer_composition"
    if semantic_review and semantic_review.get("verdict") == "gap":
        return str(semantic_review.get("attribution"))
    return "none"


def _reject_sensitive_values(value: Any, *, index: Any) -> None:
    serialized = json.dumps(value, ensure_ascii=False)
    if any(pattern.search(serialized) for pattern in _REAL_SECRET_PATTERNS):
        raise ValueError(f"source row {index}: appears to contain a real secret")
    if _REAL_EVM_ADDRESS.search(serialized):
        raise ValueError(f"source row {index}: contains a real-looking wallet address")


def _stable_case_id(question: str) -> str:
    digest = hashlib.sha256(question.encode("utf-8")).hexdigest()[:12]
    return f"approved_{digest}"


def _infer_locale(text: str) -> str:
    return "zh" if re.search(r"[\u3400-\u9fff]", text) else "en"


def _read_rows(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        value = json.loads(text)
        if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
            raise ValueError(f"{path}: JSON input must be an array of objects")
        return list(value)
    if text.startswith("{"):
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            value = None
        if value is not None:
            if not isinstance(value, dict):
                raise ValueError(f"{path}: JSON input must be an object")
            nested = value.get("cases")
            if nested is None:
                return [value]
            if not isinstance(nested, list) or not all(
                isinstance(row, dict) for row in nested
            ):
                raise ValueError(f"{path}: cases must be an array of objects")
            return list(nested)
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_no}: row must be an object")
        rows.append(value)
    return rows


def _write_json(value: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="normalize an approved Q&A batch")
    ingest.add_argument("--input", type=Path, required=True)
    ingest.add_argument("--output", type=Path, required=True)
    ingest.add_argument("--approved-by", required=True)
    ingest.add_argument("--source-version", required=True)
    ingest.add_argument("--existing", type=Path)

    target_truth = subparsers.add_parser(
        "target-truth",
        help="derive sanitized dynamic truth from Marketplace ai-context JSON",
    )
    target_truth.add_argument("--context", type=Path, required=True)
    target_truth.add_argument("--output", type=Path, required=True)

    preflight = subparsers.add_parser(
        "preflight", help="freeze approved cases and target truth before live replay"
    )
    preflight.add_argument("--cases", type=Path, required=True)
    preflight.add_argument("--target-truth", type=Path)
    preflight.add_argument("--output", type=Path, required=True)

    report = subparsers.add_parser("report", help="build an optimization gap report")
    report.add_argument("--cases", type=Path, required=True)
    report.add_argument("--baseline", type=Path, required=True)
    report.add_argument("--semantic-reviews", type=Path)
    report.add_argument(
        "--target-truth",
        type=Path,
        help="Sanitized current-Agent truth used by dynamic fact rules.",
    )
    report.add_argument("--output", type=Path, required=True)
    report.add_argument("--strict-hard", action="store_true")

    decision = subparsers.add_parser(
        "decision", help="enforce the repeated-failure rerun budget"
    )
    decision.add_argument("--report", type=Path, required=True)
    decision.add_argument("--previous-report", type=Path, action="append", default=[])
    decision.add_argument("--max-same-failure-rounds", type=int, default=2)
    decision.add_argument("--output", type=Path, required=True)

    closeout = subparsers.add_parser(
        "closeout", help="require one complete unspliced full-suite acceptance"
    )
    closeout.add_argument("--cases", type=Path, required=True)
    closeout.add_argument("--preflight", type=Path, required=True)
    closeout.add_argument("--baseline", type=Path, required=True)
    closeout.add_argument("--report", type=Path, required=True)
    closeout.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if args.command == "ingest":
        source_rows = _read_rows(args.input)
        existing_rows = load_approved_cases(args.existing) if args.existing else []
        rows = normalize_approved_cases(
            source_rows,
            approved_by=args.approved_by,
            source_version=args.source_version,
            existing_rows=existing_rows,
        )
        write_jsonl(rows, args.output)
        print(f"approved golden cases: {len(rows)} -> {args.output}")
        return 0

    if args.command == "target-truth":
        context = json.loads(args.context.read_text(encoding="utf-8"))
        output = build_target_truth_from_marketplace_context(context)
        _write_json(output, args.output)
        print(f"approved golden target truth -> {args.output}")
        return 0

    if args.command == "preflight":
        cases = load_approved_cases(args.cases)
        truth = (
            json.loads(args.target_truth.read_text(encoding="utf-8"))
            if args.target_truth
            else None
        )
        output = build_preflight_contract(cases, target_truth=truth)
        _write_json(output, args.output)
        print(f"approved golden preflight {output['status']} -> {args.output}")
        return 0 if output["status"] == "ready" else 1

    if args.command == "decision":
        report = json.loads(args.report.read_text(encoding="utf-8"))
        previous = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in args.previous_report
        ]
        output = build_iteration_decision(
            report,
            previous_reports=previous,
            max_same_failure_rounds=args.max_same_failure_rounds,
        )
        _write_json(output, args.output)
        print(f"approved golden iteration {output['decision']} -> {args.output}")
        return 1 if output["rerun_budget_exhausted"] else 0

    if args.command == "closeout":
        cases = load_approved_cases(args.cases)
        preflight = json.loads(args.preflight.read_text(encoding="utf-8"))
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        report = json.loads(args.report.read_text(encoding="utf-8"))
        output = build_closeout_report(cases, preflight, baseline, report)
        _write_json(output, args.output)
        print(f"approved golden closeout {output['status']} -> {args.output}")
        return 0

    cases = load_approved_cases(args.cases)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    reviews = _read_rows(args.semantic_reviews) if args.semantic_reviews else None
    target_truth = (
        json.loads(args.target_truth.read_text(encoding="utf-8"))
        if args.target_truth
        else None
    )
    output = build_optimization_report(
        cases,
        baseline,
        semantic_reviews=reviews,
        target_truth=target_truth,
    )
    _write_json(output, args.output)
    print(f"approved golden case report {output['status']} -> {args.output}")
    if args.strict_hard and output["release_blockers"]:
        for blocker in output["release_blockers"]:
            print(f"BLOCKER {blocker}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
