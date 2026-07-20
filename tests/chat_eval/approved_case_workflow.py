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

from tests.chat_eval.evaluator import validate_cases


SCHEMA_VERSION = "approved-golden-case-v1"
SEMANTIC_VERDICTS = {"pass", "gap", "accepted_variance"}
ATTRIBUTIONS = {
    "none",
    "prompt_or_answer_composition",
    "rag_or_retrieval",
    "tool_or_data",
    "guardrail_or_policy",
    "runtime_or_transport",
    "product_behavior",
}
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


def build_optimization_report(
    cases: list[dict[str, Any]],
    baseline_report: dict[str, Any],
    *,
    semantic_reviews: Iterable[dict[str, Any]] | None = None,
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

    results: list[dict[str, Any]] = []
    release_blockers: list[str] = []
    completion_blockers: list[str] = []
    review_packet: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case["id"])
        baseline = baseline_by_id.get(case_id)
        answer = str((baseline or {}).get("content") or "")
        transport_ok = bool(
            baseline
            and baseline.get("status") == "completed"
            and answer.strip()
        )
        required_groups = _fact_groups(case)
        missing_groups = (
            [group for group in required_groups if not _group_matches(group, answer)]
            if transport_ok
            else required_groups
        )
        forbidden = _forbidden_claims(case)
        forbidden_hits = [claim for claim in forbidden if _contains(answer, claim)]
        hard_pass = transport_ok and not missing_groups and not forbidden_hits
        review = review_by_id.get(case_id)
        semantic_verdict = str((review or {}).get("verdict") or "pending")
        attribution = _suggest_attribution(
            case,
            transport_ok=transport_ok,
            missing_groups=missing_groups,
            forbidden_hits=forbidden_hits,
            semantic_review=review,
        )

        if not transport_ok:
            release_blockers.append(f"{case_id}: live baseline missing or failed")
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
            review_packet.append(_semantic_review_item(case, answer))

    hard_failure_count = sum(not item["hard_pass"] for item in results)
    semantic_pending_count = sum(
        item["semantic_verdict"] == "pending" for item in results
    )
    semantic_gap_count = sum(item["semantic_verdict"] == "gap" for item in results)
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
        "summary": {
            "case_count": len(results),
            "hard_failure_count": hard_failure_count,
            "semantic_pending_count": semantic_pending_count,
            "semantic_gap_count": semantic_gap_count,
            "semantic_pass_or_accepted_count": sum(
                item["semantic_verdict"] in {"pass", "accepted_variance"}
                for item in results
            ),
        },
        "coverage": _coverage_summary(cases),
        "release_blockers": release_blockers,
        "completion_blockers": completion_blockers,
        "case_results": results,
        "semantic_review_packet": review_packet,
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
    for field in (
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
    _reject_sensitive_values(row, index=case_id)


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


def _semantic_review_item(case: dict[str, Any], answer: str) -> dict[str, Any]:
    return {
        "case_id": case["id"],
        "judge_mode": "llm_judge_advisory",
        "question": case["user_message"],
        "ideal_answer": case["ideal_answer"],
        "actual_answer": answer,
        "risk_level": case.get("risk_level", "low"),
        "quality_axes": case.get("quality_axes", []),
        "instruction": (
            "Judge semantic equivalence, factual completeness, and boundary safety. "
            "Do not require matching wording. Return one JSON object using the output schema."
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


def _normalize_text(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", str(value).casefold()).split())


def _suggest_attribution(
    case: dict[str, Any],
    *,
    transport_ok: bool,
    missing_groups: list[list[str]],
    forbidden_hits: list[str],
    semantic_review: dict[str, Any] | None,
) -> str:
    if not transport_ok:
        return "runtime_or_transport"
    if forbidden_hits:
        return "guardrail_or_policy"
    if missing_groups:
        if case.get("requires_tool") or case.get("expected_fields"):
            return "tool_or_data"
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

    report = subparsers.add_parser("report", help="build an optimization gap report")
    report.add_argument("--cases", type=Path, required=True)
    report.add_argument("--baseline", type=Path, required=True)
    report.add_argument("--semantic-reviews", type=Path)
    report.add_argument("--output", type=Path, required=True)
    report.add_argument("--strict-hard", action="store_true")
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

    cases = load_approved_cases(args.cases)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    reviews = _read_rows(args.semantic_reviews) if args.semantic_reviews else None
    output = build_optimization_report(cases, baseline, semantic_reviews=reviews)
    _write_json(output, args.output)
    print(f"approved golden case report {output['status']} -> {args.output}")
    if args.strict_hard and output["release_blockers"]:
        for blocker in output["release_blockers"]:
            print(f"BLOCKER {blocker}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
