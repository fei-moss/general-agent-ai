from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from test_cases import generate_tests_from_path


MOSS_GOLDEN_PATH = Path(__file__).with_name("moss_golden_queries.jsonl")


def generate_tests() -> list[dict[str, Any]]:
    """Generate Promptfoo cases for reviewed MOSS Wiki Golden Queries."""
    return generate_tests_from_path(MOSS_GOLDEN_PATH)
