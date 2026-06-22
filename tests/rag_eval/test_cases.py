from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_GOLDEN_PATH = Path(__file__).with_name("golden_queries.jsonl")


def generate_tests() -> list[dict[str, Any]]:
    """Generate Promptfoo test cases from golden query JSONL."""
    return generate_tests_from_path(DEFAULT_GOLDEN_PATH)


def generate_tests_from_path(path: Path) -> list[dict[str, Any]]:
    """Generate Promptfoo test cases from an explicit golden query file."""
    cases: list[dict[str, Any]] = []
    for row in _load_jsonl(path):
        query = str(row["query"]).strip()
        cases.append(
            {
                "description": row["id"],
                "vars": {
                    "query": query,
                    "relevant_doc_ids": ",".join(row["relevant_doc_ids"]),
                    "max_rank": row.get("max_rank", row.get("top_k", 3)),
                    "top_k": row.get("top_k", 3),
                    "tags": ",".join(row.get("tags", [])),
                },
                "assert": [
                    {
                        "type": "python",
                        "value": "file://assert_retrieval.py",
                    }
                ],
            }
        )
    return cases


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"RAG eval golden queries not found: {path}")
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not row.get("id") or not row.get("query") or not row.get("relevant_doc_ids"):
            raise ValueError(f"invalid golden query row at {path}:{line_no}")
        rows.append(row)
    if not rows:
        raise ValueError(f"RAG eval golden queries are empty: {path}")
    return rows
