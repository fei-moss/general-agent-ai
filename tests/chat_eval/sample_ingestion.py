"""Sanitize online chat samples into candidate chat eval golden cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


_SECRET_PATTERNS = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.I),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
_REAL_EVM_ADDRESS = re.compile(r"\b0x(?!Eval)[a-fA-F0-9]{40}\b")
_TRACE_LIKE = re.compile(r"\b(?:run|trace|conv)_[A-Za-z0-9]{16,}\b")


def sanitize_sample(value: Any) -> Any:
    """Recursively redact secrets, wallets, and trace-like ids."""
    if isinstance(value, dict):
        return {str(key): sanitize_sample(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_sample(item) for item in value]
    if not isinstance(value, str):
        return value
    text = value
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("<redacted-secret>", text)
    text = _REAL_EVM_ADDRESS.sub("<redacted-address>", text)
    text = _TRACE_LIKE.sub("<redacted-trace-id>", text)
    return text


def candidate_case_from_sample(sample: dict[str, Any]) -> dict[str, Any]:
    """Create a reviewable golden-case candidate from a sanitized sample."""
    sanitized = sanitize_sample(sample)
    user_message = str(
        sanitized.get("user_message")
        or sanitized.get("message")
        or sanitized.get("input")
        or ""
    ).strip()
    if not user_message:
        raise ValueError("sample requires user_message/message/input")
    area = str(sanitized.get("area") or "triage_candidate")
    tags = [str(tag) for tag in sanitized.get("tags", [])] or ["candidate"]
    failure_reason = str(sanitized.get("failure_reason") or "needs_review")
    case_id = "candidate_" + hashlib.sha256(
        f"{area}:{user_message}:{failure_reason}".encode("utf-8")
    ).hexdigest()[:12]
    return {
        "id": case_id,
        "locale": str(sanitized.get("locale") or "zh"),
        "area": area,
        "user_message": user_message,
        "expected_input_action": str(
            sanitized.get("expected_input_action") or "allow"
        ),
        "expected_input_category": str(
            sanitized.get("expected_input_category") or "allowed"
        ),
        "requires_rag": bool(sanitized.get("requires_rag", False)),
        "requires_tool": sanitized.get("requires_tool"),
        "answer_traits": [
            str(item)
            for item in sanitized.get(
                "answer_traits", ["修复线上坏样本", "遵守 Ask this Agent 边界"]
            )
        ],
        "forbidden_claims": [
            str(item)
            for item in sanitized.get(
                "forbidden_claims", ["重复线上错误回答", "<redacted-secret>"]
            )
        ],
        "risk_level": str(sanitized.get("risk_level") or "medium"),
        "quality_axes": [
            str(item)
            for item in sanitized.get(
                "quality_axes", ["correctness", "boundary_safety"]
            )
        ],
        "tags": sorted(set(tags + ["candidate", "online_sample"])),
        "review_note": failure_reason,
    }


def convert_samples(input_path: Path, output_path: Path) -> int:
    """Convert a JSONL sample file into candidate golden cases."""
    count = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with input_path.open(encoding="utf-8") as source, output_path.open(
        "w", encoding="utf-8"
    ) as sink:
        for line_no, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                sample = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{input_path}:{line_no}: invalid JSON") from exc
            if not isinstance(sample, dict):
                raise ValueError(f"{input_path}:{line_no}: sample must be an object")
            sink.write(
                json.dumps(
                    candidate_case_from_sample(sample),
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )
            count += 1
    return count


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    count = convert_samples(args.input, args.output)
    print(f"wrote {count} candidate chat eval cases -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
