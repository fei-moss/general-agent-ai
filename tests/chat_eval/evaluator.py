"""Deterministic chat behavior eval fixture loader and validator."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.runtime.chat_behavior import GuardrailAction, GuardrailCategory

CASE_FILE = Path(__file__).with_name("golden_cases.jsonl")
COVERAGE_CONTRACT_FILE = Path(__file__).with_name("coverage_contract.json")
ANSWER_RUBRIC_FILE = Path(__file__).with_name("answer_rubric.json")

_REQUIRED_FIELDS = {
    "id",
    "locale",
    "area",
    "user_message",
    "expected_input_action",
    "expected_input_category",
    "requires_rag",
    "requires_tool",
    "tags",
}
_ALLOWED_ACTIONS = {action.value for action in GuardrailAction}
_ALLOWED_CATEGORIES = {category.value for category in GuardrailCategory}
_ALLOWED_RISK_LEVELS = {"low", "medium", "high", "critical"}
_OPTIONAL_LIST_FIELDS = {
    "applicable_agent_brands",
    "applicable_agent_types",
    "dynamic_fact_variables",
    "dynamic_fact_rules",
    "expected_sources",
    "expected_fields",
    "quality_axes",
    "expected_tool_events",
}
_SECRET_VALUE_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
_EVM_ADDRESS_PATTERN = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
_SYNTHETIC_EVM_PATTERN = re.compile(r"\b0xEval[a-zA-Z0-9]{8,}\b")


@dataclass(frozen=True)
class ChatBehaviorCase:
    """Validated chat behavior golden case."""

    raw: dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.raw["id"])

    @property
    def user_message(self) -> str:
        return str(self.raw["user_message"])

    @property
    def expected_input_action(self) -> str:
        return str(self.raw["expected_input_action"])

    @property
    def expected_input_category(self) -> str:
        return str(self.raw["expected_input_category"])

    @property
    def sample_assistant_answer(self) -> str | None:
        value = self.raw.get("sample_assistant_answer")
        return None if value is None else str(value)

    @property
    def target_language(self) -> str:
        return str(self.raw.get("target_language") or "unknown")


def load_cases(
    path: Path = CASE_FILE,
    *,
    min_cases: int | None = None,
) -> list[ChatBehaviorCase]:
    """Load and validate chat behavior golden cases."""
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AssertionError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise AssertionError(f"{path}:{line_no}: case must be an object")
            rows.append(row)
    effective_minimum = (
        min_cases if min_cases is not None else (10 if path == CASE_FILE else 1)
    )
    errors = validate_cases(rows, min_cases=effective_minimum)
    if errors:
        joined = "\n".join(errors)
        raise AssertionError(f"invalid chat behavior golden cases:\n{joined}")
    return [ChatBehaviorCase(row) for row in rows]


def load_coverage_contract(
    path: Path = COVERAGE_CONTRACT_FILE,
) -> dict[str, Any]:
    """Load the Ask this Agent chat eval coverage contract."""
    with path.open(encoding="utf-8") as handle:
        contract = json.load(handle)
    if not isinstance(contract, dict):
        raise AssertionError(f"{path}: coverage contract must be an object")
    return contract


def load_answer_rubric(path: Path = ANSWER_RUBRIC_FILE) -> dict[str, Any]:
    """Load the answer quality rubric used by scorecards."""
    with path.open(encoding="utf-8") as handle:
        rubric = json.load(handle)
    if not isinstance(rubric, dict):
        raise AssertionError(f"{path}: answer rubric must be an object")
    return rubric


def validate_cases(
    rows: list[dict[str, Any]],
    *,
    min_cases: int = 10,
) -> list[str]:
    """Return validation errors for raw case dictionaries."""
    errors: list[str] = []
    ids: set[str] = set()
    for idx, row in enumerate(rows, start=1):
        case_id = str(row.get("id") or f"line_{idx}")
        missing = sorted(_REQUIRED_FIELDS - set(row))
        if missing:
            errors.append(f"{case_id}: missing fields {missing}")
        if case_id in ids:
            errors.append(f"{case_id}: duplicate id")
        ids.add(case_id)
        _validate_scalar(row, "id", errors, case_id)
        _validate_scalar(row, "locale", errors, case_id)
        _validate_scalar(row, "area", errors, case_id)
        _validate_scalar(row, "user_message", errors, case_id)
        _validate_enum(
            row, "expected_input_action", _ALLOWED_ACTIONS, errors, case_id
        )
        _validate_enum(
            row, "expected_input_category", _ALLOWED_CATEGORIES, errors, case_id
        )
        if row.get("expected_input_action") == "refuse":
            _validate_string_list(row, "safe_response_contains", errors, case_id)
        if row.get("expected_input_action") == "allow":
            dynamic_only_approved_case = bool(
                row.get("schema_version") == "approved-golden-case-v1"
                and row.get("dynamic_fact_rules")
                and row.get("answer_traits") == []
            )
            if not dynamic_only_approved_case:
                _validate_string_list(row, "answer_traits", errors, case_id)
            if not (
                row.get("schema_version") == "approved-golden-case-v1"
                and row.get("forbidden_claims") == []
            ):
                _validate_string_list(row, "forbidden_claims", errors, case_id)
        if "expected_output_action" in row:
            _validate_enum(
                row, "expected_output_action", _ALLOWED_ACTIONS, errors, case_id
            )
            _validate_enum(
                row,
                "expected_output_category",
                _ALLOWED_CATEGORIES,
                errors,
                case_id,
            )
            if not row.get("sample_assistant_answer"):
                errors.append(f"{case_id}: output case needs sample_assistant_answer")
        if "risk_level" in row:
            _validate_enum(row, "risk_level", _ALLOWED_RISK_LEVELS, errors, case_id)
        if "requires_wallet" in row and not isinstance(row["requires_wallet"], bool):
            errors.append(f"{case_id}: requires_wallet must be a boolean")
        if "fixture_proxy_payload" in row and not isinstance(
            row["fixture_proxy_payload"], dict
        ):
            errors.append(f"{case_id}: fixture_proxy_payload must be an object")
        for field in _OPTIONAL_LIST_FIELDS:
            if field in row:
                _validate_string_list(row, field, errors, case_id)
        _validate_string_list(row, "tags", errors, case_id)
        _validate_secret_hygiene(row, errors, case_id)
        _validate_wallet_hygiene(row, errors, case_id)
    if len(rows) < min_cases:
        errors.append(f"fixture must contain at least {min_cases} cases")
    return errors


def validate_coverage_contract(
    cases: list[ChatBehaviorCase],
    contract: dict[str, Any] | None = None,
    rubric: dict[str, Any] | None = None,
) -> list[str]:
    """Return coverage errors for the current golden case dataset."""
    contract = contract or load_coverage_contract()
    rubric = rubric or load_answer_rubric()
    errors: list[str] = []
    rows = [case.raw for case in cases]
    if len(rows) < int(contract.get("min_total_cases", 0)):
        errors.append(
            f"case_count {len(rows)} below min_total_cases {contract['min_total_cases']}"
        )
    areas = _count_values(row.get("area") for row in rows)
    for area, minimum in dict(contract.get("required_areas", {})).items():
        actual = areas.get(str(area), 0)
        if actual < int(minimum):
            errors.append(f"area {area} has {actual}, needs {minimum}")
    tags = set()
    for row in rows:
        tags.update(str(tag) for tag in row.get("tags", []))
    for tag in contract.get("required_tags", []):
        if str(tag) not in tags:
            errors.append(f"required tag {tag} missing")
    required_axes = {str(axis) for axis in contract.get("required_quality_axes", [])}
    rubric_axes = set(dict(rubric.get("dimensions", {})))
    missing_rubric_axes = required_axes - rubric_axes
    if missing_rubric_axes:
        errors.append(f"rubric missing axes {sorted(missing_rubric_axes)}")
    case_axes = set()
    for row in rows:
        case_axes.update(str(axis) for axis in row.get("quality_axes", []))
    for axis in required_axes:
        if axis not in case_axes:
            errors.append(f"quality axis {axis} missing from cases")
    for level, spec in dict(contract.get("risk_levels", {})).items():
        minimum = int(dict(spec).get("min_cases", 0))
        actual = sum(1 for row in rows if row.get("risk_level") == level)
        if actual < minimum:
            errors.append(f"risk_level {level} has {actual}, needs {minimum}")
    _validate_data_consistency_coverage(rows, contract, errors)
    _validate_wallet_coverage(rows, contract, errors)
    return errors


def coverage_summary(cases: list[ChatBehaviorCase]) -> dict[str, int]:
    """Return simple coverage counters used by pytest gates."""
    counts: dict[str, int] = {
        "allow": 0,
        "refuse": 0,
        "rag_required": 0,
        "hidden_instruction": 0,
        "secret_request": 0,
        "real_money_operation": 0,
        "personal_wallet_data": 0,
        "output_policy_leak": 0,
        "language_mismatch": 0,
        "false_positive_guard": 0,
    }
    for case in cases:
        action = case.expected_input_action
        if action in counts:
            counts[action] += 1
        category = case.expected_input_category
        if category in counts:
            counts[category] += 1
        if case.raw.get("requires_rag") is True:
            counts["rag_required"] += 1
        if case.raw.get("expected_output_category") == "output_policy_leak":
            counts["output_policy_leak"] += 1
        if case.raw.get("expected_output_category") == "language_mismatch":
            counts["language_mismatch"] += 1
        if "false_positive_guard" in case.raw.get("tags", []):
            counts["false_positive_guard"] += 1
    return counts


def data_consistency_cases(cases: list[ChatBehaviorCase]) -> list[ChatBehaviorCase]:
    """Return cases that declare expected sources or fields."""
    return [
        case
        for case in cases
        if case.raw.get("expected_sources") or case.raw.get("expected_fields")
    ]


def _validate_scalar(
    row: dict[str, Any], field: str, errors: list[str], case_id: str
) -> None:
    if field in row and not str(row[field]).strip():
        errors.append(f"{case_id}: {field} must be non-empty")


def _validate_enum(
    row: dict[str, Any],
    field: str,
    allowed: set[str],
    errors: list[str],
    case_id: str,
) -> None:
    if field in row and row[field] not in allowed:
        errors.append(f"{case_id}: {field}={row[field]!r} not in {sorted(allowed)}")


def _validate_string_list(
    row: dict[str, Any], field: str, errors: list[str], case_id: str
) -> None:
    value = row.get(field)
    if not isinstance(value, list) or not value:
        errors.append(f"{case_id}: {field} must be a non-empty list")
        return
    for item in value:
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{case_id}: {field} items must be non-empty strings")


def _validate_secret_hygiene(
    row: dict[str, Any], errors: list[str], case_id: str
) -> None:
    serialized = json.dumps(row, ensure_ascii=False)
    for pattern in _SECRET_VALUE_PATTERNS:
        if pattern.search(serialized):
            errors.append(f"{case_id}: fixture appears to contain a real secret")


def _validate_wallet_hygiene(
    row: dict[str, Any], errors: list[str], case_id: str
) -> None:
    serialized = json.dumps(row, ensure_ascii=False)
    scrubbed = _SYNTHETIC_EVM_PATTERN.sub("", serialized)
    if _EVM_ADDRESS_PATTERN.search(scrubbed):
        errors.append(
            f"{case_id}: fixture contains a real-looking wallet/address; use a synthetic 0xEval... value"
        )


def _validate_data_consistency_coverage(
    rows: list[dict[str, Any]],
    contract: dict[str, Any],
    errors: list[str],
) -> None:
    spec = dict(contract.get("data_consistency", {}))
    data_rows = [
        row for row in rows if row.get("expected_sources") or row.get("expected_fields")
    ]
    minimum = int(spec.get("min_cases", 0))
    if len(data_rows) < minimum:
        errors.append(f"data_consistency cases {len(data_rows)} below {minimum}")
    sources = set()
    fields = set()
    for row in data_rows:
        sources.update(str(item) for item in row.get("expected_sources", []))
        fields.update(str(item) for item in row.get("expected_fields", []))
    for source in spec.get("required_sources", []):
        if str(source) not in sources:
            errors.append(f"data_consistency source {source} missing")
    for field in spec.get("required_fields", []):
        if str(field) not in fields:
            errors.append(f"data_consistency field {field} missing")


def _validate_wallet_coverage(
    rows: list[dict[str, Any]],
    contract: dict[str, Any],
    errors: list[str],
) -> None:
    spec = dict(contract.get("wallet_context", {}))
    wallet_rows = [row for row in rows if row.get("requires_wallet") is True]
    minimum = int(spec.get("min_cases", 0))
    if len(wallet_rows) < minimum:
        errors.append(f"wallet_context cases {len(wallet_rows)} below {minimum}")
    prefix = str(spec.get("synthetic_address_prefix") or "")
    if not prefix:
        return
    for row in wallet_rows:
        payload = row.get("fixture_proxy_payload")
        serialized = json.dumps(payload, ensure_ascii=False)
        if prefix not in serialized:
            errors.append(f"{row.get('id')}: wallet case must use {prefix} payload")


def _count_values(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return counts
