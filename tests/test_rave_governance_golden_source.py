from __future__ import annotations

import hashlib
from pathlib import Path


_VENDORED_SOURCE = (
    Path(__file__).parent
    / "chat_eval"
    / "fixtures"
    / "rave_governance_golden_source_20260821.md"
)
_VENDORED_SOURCE_SHA256 = (
    "47c20ff3f536263f34089b20e7e72006c4f61300d6d1a543db6ffc162d2b0eb5"
)


def test_rave_governance_owner_source_is_vendored_verbatim_and_hash_pinned():
    payload = _VENDORED_SOURCE.read_bytes()
    text = payload.decode("utf-8")

    assert hashlib.sha256(payload).hexdigest() == _VENDORED_SOURCE_SHA256
    assert text.count("Q：") == 43
    assert text.count("【按实际规则填】") == 4
    assert text.startswith("# Ask This Agent｜Rave Governance Agent(owner 提供,2026-08-21)\n")

