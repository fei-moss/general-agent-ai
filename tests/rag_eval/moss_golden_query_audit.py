from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = Path(".artifacts/release/moss_golden_query_audit.json")
SOURCE_LINES_RE = re.compile(r"^\d+-\d+(,\d+-\d+)*$")


def build_audit_report(
    *,
    eval_dir: Path = EVAL_DIR,
) -> dict[str, Any]:
    """Build a machine-readable audit report for reviewed MOSS Golden Queries."""
    corpus_rows = _load_jsonl(eval_dir / "moss_corpus.jsonl")
    query_rows = _load_jsonl(eval_dir / "moss_golden_queries.jsonl")
    review_rows = _load_jsonl(eval_dir / "moss_golden_query_review.jsonl")
    contract = _load_json(eval_dir / "moss_coverage_contract.json")

    query_ids = {row["id"] for row in query_rows}
    corpus_doc_ids = {row["id"] for row in corpus_rows}
    review_by_id = {row["id"]: row for row in review_rows}
    tags = {tag for row in query_rows for tag in row.get("tags", [])}
    challenge_types = {row["challenge_type"] for row in review_rows}
    multi_source_query_count = sum(1 for row in query_rows if len(row["relevant_doc_ids"]) > 1)
    review_evidence = [
        evidence
        for row in review_rows
        for evidence in row.get("source_evidence", [])
    ]
    corpus_source_urls = {
        row.get("meta", {}).get("source_url")
        for row in corpus_rows
        if row.get("meta", {}).get("source_url")
    }
    invalid_source_line_ranges = sorted(
        {
            source_lines
            for source_lines in [
                *[
                    str(row.get("meta", {}).get("source_lines", ""))
                    for row in corpus_rows
                ],
                *[
                    str(evidence.get("source_lines", ""))
                    for evidence in review_evidence
                ],
            ]
            if not SOURCE_LINES_RE.match(source_lines)
        }
    )

    missing_review_rows = sorted(query_ids - set(review_by_id))
    review_without_query = sorted(set(review_by_id) - query_ids)
    queries_missing_source_evidence = sorted(
        row["id"]
        for row in review_rows
        if not row.get("source_evidence")
    )
    queries_with_unknown_docs = sorted(
        row["id"]
        for row in query_rows
        if not set(row["relevant_doc_ids"]) <= corpus_doc_ids
    )

    capability_groups_missing_queries: list[dict[str, Any]] = []
    for group in contract["capability_groups"]:
        missing = sorted(set(group["query_ids"]) - query_ids)
        if missing:
            capability_groups_missing_queries.append(
                {"name": group["name"], "missing_query_ids": missing}
            )

    coverage = {
        "required_language_tags_missing": sorted(set(contract["required_language_tags"]) - tags),
        "required_topic_tags_missing": sorted(set(contract["required_topic_tags"]) - tags),
        "required_challenge_types_missing": sorted(
            set(contract["required_challenge_types"]) - challenge_types
        ),
        "capability_groups_missing_queries": capability_groups_missing_queries,
    }
    counts = {
        "queries": len(query_rows),
        "corpus_docs": len(corpus_rows),
        "review_rows": len(review_rows),
        "queries_with_source_evidence": len(review_rows) - len(queries_missing_source_evidence),
    }
    screening_value = {
        "multi_source_query_count": multi_source_query_count,
        "challenge_type_count": len(challenge_types),
        "language_tag_count": len(tags & set(contract["required_language_tags"])),
        "topic_tag_count": len(tags & set(contract["required_topic_tags"])),
        "capability_group_count": len(contract["capability_groups"]),
        "reviewed_source_url_count": len(
            {
                evidence["source_url"]
                for row in review_rows
                for evidence in row.get("source_evidence", [])
                if evidence.get("source_url")
            }
        ),
    }
    provenance = {
        "review_evidence_count": len(review_evidence),
        "corpus_rows_with_source_url": sum(
            1 for row in corpus_rows if row.get("meta", {}).get("source_url")
        ),
        "corpus_rows_with_source_lines": sum(
            1 for row in corpus_rows if row.get("meta", {}).get("source_lines")
        ),
        "invalid_source_line_ranges": invalid_source_line_ranges,
        "review_source_urls_without_corpus_source_url": sorted(
            {
                evidence["source_url"]
                for evidence in review_evidence
                if evidence.get("source_url") not in corpus_source_urls
            }
        ),
    }
    errors = []
    if counts["queries"] < int(contract["min_query_count"]):
        errors.append("query count below coverage contract")
    if counts["corpus_docs"] < int(contract["min_corpus_doc_count"]):
        errors.append("corpus doc count below coverage contract")
    if len(challenge_types) < int(contract["min_challenge_type_count"]):
        errors.append("challenge type count below coverage contract")
    if multi_source_query_count < int(contract["min_multi_source_queries"]):
        errors.append("multi-source query count below coverage contract")
    if missing_review_rows:
        errors.append("some golden queries lack review rows")
    if review_without_query:
        errors.append("some review rows do not map to golden queries")
    if queries_missing_source_evidence:
        errors.append("some review rows lack source evidence")
    if queries_with_unknown_docs:
        errors.append("some golden queries reference unknown corpus docs")
    if any(coverage.values()):
        errors.append("coverage contract is not fully satisfied")
    if provenance["corpus_rows_with_source_url"] != counts["corpus_docs"]:
        errors.append("some corpus rows lack source_url")
    if provenance["corpus_rows_with_source_lines"] != counts["corpus_docs"]:
        errors.append("some corpus rows lack source_lines")
    if provenance["invalid_source_line_ranges"]:
        errors.append("some source line ranges are malformed")
    if provenance["review_source_urls_without_corpus_source_url"]:
        errors.append("some review source URLs are not represented in corpus sources")

    return {
        "status": "passed" if not errors else "failed",
        "spec_id": "SPEC-RAG-EVAL-001",
        "coverage_contract_id": contract["contract_id"],
        "counts": counts,
        "coverage": coverage,
        "provenance": provenance,
        "screening_value": screening_value,
        "consistency": {
            "missing_review_rows": missing_review_rows,
            "review_without_query": review_without_query,
            "queries_missing_source_evidence": queries_missing_source_evidence,
            "queries_with_unknown_docs": queries_with_unknown_docs,
        },
        "errors": errors,
    }


def write_audit_report(
    *,
    output_path: Path = DEFAULT_OUTPUT,
    eval_dir: Path = EVAL_DIR,
) -> dict[str, Any]:
    report = build_audit_report(eval_dir=eval_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write a machine-readable audit report for MOSS Golden Queries."
    )
    parser.add_argument("--eval-dir", default=str(EVAL_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    report = write_audit_report(output_path=Path(args.output), eval_dir=Path(args.eval_dir))
    print(f"MOSS Golden Query audit {report['status']} -> {args.output}")
    if report["status"] != "passed":
        raise SystemExit(1)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


if __name__ == "__main__":
    main()
