from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from tests.rag_eval.marketplace_qna_fixture_builder import build_fixture_bundle


EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = Path(".artifacts/release/marketplace_qna_golden_query_audit.json")
_LINES_RE = re.compile(r"^\d+-\d+$")
STRUCTURAL_ANCHOR_ORDERS = {2, 6, 8, 10, 11, 12, 13, 14, 15, 16, 17}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build_audit_report(*, eval_dir: Path = EVAL_DIR) -> dict[str, Any]:
    bundle = build_fixture_bundle()
    corpus = _load_jsonl(eval_dir / "marketplace_qna_corpus.jsonl")
    queries = _load_jsonl(eval_dir / "marketplace_qna_golden_queries.jsonl")
    reviews = _load_jsonl(eval_dir / "marketplace_qna_golden_query_review.jsonl")
    chats = _load_jsonl(eval_dir / "marketplace_qna_chat_cases.jsonl")
    contract = _load_json(eval_dir / "marketplace_qna_coverage_contract.json")

    expected_query_ids = {
        question.id for source in bundle.sources for question in source.questions
    }
    source_by_id = {source.id: source for source in bundle.sources}
    question_by_id = {
        question.id: question
        for source in bundle.sources
        for question in source.questions
    }
    query_ids = {row["id"] for row in queries}
    review_ids = {row["id"] for row in reviews}
    document_ids = {row["id"] for row in corpus}
    known_source_uris = {row["meta"]["source_uri"] for row in corpus}
    invalid_source_evidence: list[str] = []
    for review in reviews:
        evidence_rows = review.get("source_evidence") or []
        if not evidence_rows:
            invalid_source_evidence.append(review["id"])
            continue
        for evidence in evidence_rows:
            source_path = Path(__file__).parents[2] / str(evidence.get("source_path") or "")
            if (
                evidence.get("source_uri") not in known_source_uris
                or not _LINES_RE.match(str(evidence.get("source_lines") or ""))
                or not source_path.is_file()
            ):
                invalid_source_evidence.append(review["id"])
                break

    missing_topic_groups = sorted(
        group["name"]
        for group in contract["topic_groups"]
        if not group.get("query_ids") or not set(group["query_ids"]) <= query_ids
    )
    gaps = {
        "missing_query_ids": sorted(expected_query_ids - query_ids),
        "unexpected_query_ids": sorted(query_ids - expected_query_ids),
        "missing_review_ids": sorted(query_ids - review_ids),
        "unknown_document_ids": sorted(
            {
                document_id
                for row in queries
                for document_id in row["relevant_doc_ids"]
                if document_id not in document_ids
            }
        ),
        "missing_topic_groups": missing_topic_groups,
        "invalid_source_evidence": sorted(set(invalid_source_evidence)),
    }
    errors = [name for name, values in gaps.items() if values]
    counts = {
        "source_documents": len(corpus),
        "golden_queries": len(queries),
        "review_rows": len(reviews),
        "chat_cases": len(chats),
        "source_questions": len(expected_query_ids),
    }
    expected_counts = {
        "source_documents": 34,
        "golden_queries": 350,
        "review_rows": 350,
        "chat_cases": 34,
        "source_questions": 350,
    }
    if counts != expected_counts:
        errors.append("count_mismatch")
    structural_anchor_audit: dict[str, dict[str, Any]] = {}
    for query in sorted(queries, key=lambda row: str(row["id"])):
        expected_doc_id = str(query["relevant_doc_ids"][0])
        source = source_by_id.get(expected_doc_id)
        question = question_by_id.get(str(query["id"]))
        if source is None or question is None or source.order not in STRUCTURAL_ANCHOR_ORDERS:
            continue
        structural_anchor_audit[str(query["id"])] = {
            "query": str(query["query"]),
            "expected_doc_id": expected_doc_id,
            "section_heading": question.question,
            "source_path": source.path.relative_to(Path(__file__).parents[2]).as_posix(),
            "answer_lines": f"{question.answer_start_line}-{question.answer_end_line}",
        }
    return {
        "status": "passed" if not errors else "failed",
        "spec_id": "SPEC-RAG-EVAL-002",
        "coverage_contract_id": contract["contract_id"],
        "counts": counts,
        "gaps": gaps,
        "errors": errors,
        "structural_anchor_audit": structural_anchor_audit,
    }


def write_audit_report(*, output_path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    report = build_audit_report()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Marketplace QnA Golden Cases")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    report = write_audit_report(output_path=Path(args.output))
    print(f"Marketplace QnA Golden Query audit {report['status']} -> {args.output}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
