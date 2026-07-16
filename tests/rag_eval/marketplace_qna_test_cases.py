from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from test_cases import generate_tests_from_path


GOLDEN_PATH = MODULE_DIR / "marketplace_qna_golden_queries.jsonl"


def generate_tests() -> list[dict[str, Any]]:
    cases = generate_tests_from_path(GOLDEN_PATH)
    for case in cases:
        tags = {tag.strip() for tag in str(case["vars"].get("tags") or "").split(",")}
        languages = tags & {"zh-CN", "en"}
        if len(languages) != 1:
            raise ValueError(f"case must have exactly one language tag: {case['description']}")
        case["vars"]["language"] = languages.pop()
    return cases
