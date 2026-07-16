"""Validate all Marketplace QnA ingestion and evaluation evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parents[1]
DEFAULT_CONTRACT_PATH = EVAL_DIR / "marketplace_qna_acceptance_evidence_contract.json"
_IDENTITY_PATTERNS = (
    re.compile(r"marketplace:user:\d+", re.I),
    re.compile(r"\b0x[a-fA-F0-9]{40}\b"),
    re.compile(r"\bBearer\s+\S+", re.I),
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact(root: Path, section: dict[str, Any]) -> tuple[Path, dict[str, Any] | None, list[str]]:
    artifact_path = section.get("artifact_path") or section.get("summary_artifact_path")
    if not artifact_path:
        return root, None, ["acceptance contract section has no artifact path"]
    path = root / artifact_path
    if not path.exists():
        return path, None, [f"missing artifact {artifact_path}"]
    try:
        return path, _load_json(path), []
    except Exception as exc:  # noqa: BLE001 - validation reports malformed evidence
        return path, None, [f"invalid artifact {artifact_path}: {exc}"]


def validate_acceptance(
    *,
    root: Path = REPO_ROOT,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
) -> list[str]:
    contract = _load_json(contract_path)
    thresholds = contract["thresholds"]
    errors: list[str] = []
    errors.extend(_validate_audit(root, contract["fixture_audit"], thresholds))
    errors.extend(_validate_ingestion(root, contract["ingestion"], thresholds))
    errors.extend(_validate_promptfoo(root, contract["promptfoo"], thresholds))
    errors.extend(
        _validate_live_retrieval(root, contract["live_retrieval"], thresholds)
    )
    errors.extend(_validate_live_chat(root, contract["live_chat"], thresholds))
    errors.extend(_validate_release(root, contract["release_gate"]))
    return errors


def _validate_audit(
    root: Path, section: dict[str, Any], thresholds: dict[str, Any]
) -> list[str]:
    _, payload, errors = _artifact(root, section)
    if payload is None:
        return [f"fixture_audit: {error}" for error in errors]
    output: list[str] = []
    if payload.get("status") != section["required_status"]:
        output.append(f"fixture_audit: status={payload.get('status')} expected passed")
    counts = payload.get("counts") or {}
    for field, threshold in (
        ("source_documents", thresholds["source_documents"]),
        ("golden_queries", thresholds["golden_queries"]),
        ("chat_cases", thresholds["chat_cases"]),
    ):
        if int(counts.get(field) or 0) != int(threshold):
            output.append(f"fixture_audit: {field} count mismatch")
    return output


def _validate_ingestion(
    root: Path, section: dict[str, Any], thresholds: dict[str, Any]
) -> list[str]:
    _, payload, errors = _artifact(root, section)
    if payload is None:
        return [f"ingestion: {error}" for error in errors]
    output: list[str] = []
    expected_documents = int(thresholds["source_documents"])
    for field in ("submitted_documents", "persisted_documents", "succeeded_jobs"):
        if int(payload.get(field) or 0) != expected_documents:
            output.append(f"ingestion: {field} expected {expected_documents}")
    if int(payload.get("failed_jobs") or 0) > int(
        thresholds["maximum_failed_ingestion_jobs"]
    ):
        output.append(f"ingestion: failed_jobs={payload.get('failed_jobs')}")
    if int(payload.get("persisted_chunks") or 0) != int(section["expected_chunks"]):
        output.append("ingestion: persisted_chunks mismatch")
    for field, expected in (
        ("embedding_provider", section["required_embedding_provider"]),
        ("embedding_model", section["required_embedding_model"]),
        ("embedding_dim", section["required_embedding_dimension"]),
    ):
        if payload.get(field) != expected:
            output.append(f"ingestion: {field} mismatch")
    if not bool((payload.get("source_hash_audit") or {}).get("hash_maps_equal")):
        output.append("ingestion: source hashes do not match the upload manifest")
    return output


def _expected_doc_ids(row: dict[str, Any]) -> set[str]:
    variables = ((row.get("testCase") or {}).get("vars") or row.get("vars") or {})
    raw = variables.get("relevant_doc_ids") or []
    if isinstance(raw, str):
        return {item.strip() for item in raw.split(",") if item.strip()}
    return {str(item) for item in raw}


def _promptfoo_top1_rate(rows: list[dict[str, Any]]) -> float:
    top1 = 0
    for row in rows:
        try:
            output = json.loads((row.get("response") or {})["output"])
            first = (output.get("hits") or [])[0]
            if str(first.get("doc_id")) in _expected_doc_ids(row):
                top1 += 1
        except Exception:  # noqa: BLE001 - malformed rows simply do not count top1
            continue
    return top1 / len(rows) if rows else 0.0


def _validate_promptfoo(
    root: Path, section: dict[str, Any], thresholds: dict[str, Any]
) -> list[str]:
    _, payload, errors = _artifact(root, section)
    if payload is None:
        return [f"promptfoo: {error}" for error in errors]
    try:
        result_block = payload["results"]
        stats = result_block["stats"]
        rows = result_block["results"]
    except Exception as exc:  # noqa: BLE001
        return [f"promptfoo: invalid result shape: {exc}"]
    expected = int(thresholds["promptfoo_required_passes"])
    successes = int(stats.get("successes") or 0)
    failures = int(stats.get("failures") or 0)
    error_count = int(stats.get("errors") or 0)
    output: list[str] = []
    if len(rows) != expected or successes != expected or failures or error_count:
        output.append(
            "promptfoo: expected "
            f"{expected} passes, got successes={successes}, failures={failures}, "
            f"errors={error_count}, rows={len(rows)}"
        )
    top1_rate = _promptfoo_top1_rate(rows)
    if top1_rate < float(thresholds["minimum_top1_rate"]):
        output.append(
            f"promptfoo: top1_rate={top1_rate:.4f} below "
            f"{thresholds['minimum_top1_rate']}"
        )
    return output


def _contains_runtime_identity(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return any(pattern.search(text) for pattern in _IDENTITY_PATTERNS)


def _validate_live_retrieval(
    root: Path, section: dict[str, Any], thresholds: dict[str, Any]
) -> list[str]:
    path, payload, errors = _artifact(root, section)
    if payload is None:
        return [f"live_retrieval: {error}" for error in errors]
    counts = payload.get("counts") or {}
    rows = payload.get("results") or []
    required = int(thresholds["live_required_passes"])
    output: list[str] = []
    if payload.get("status") != "passed" or int(counts.get("passed") or 0) != required:
        output.append(
            f"live_retrieval: passed={counts.get('passed')} expected {required}"
        )
    if len(rows) != required or any(not row.get("passed") for row in rows):
        output.append("live_retrieval: result rows are incomplete or failed")
    if int(counts.get("degraded") or 0) > int(
        thresholds["maximum_degraded_cases"]
    ):
        output.append(f"live_retrieval: degraded={counts.get('degraded')}")
    if float(payload.get("top1_rate") or 0.0) < float(
        thresholds["minimum_top1_rate"]
    ):
        output.append(
            f"live_retrieval: top1_rate={payload.get('top1_rate')} below "
            f"{thresholds['minimum_top1_rate']}"
        )
    if _contains_runtime_identity(path):
        output.append("live_retrieval: runtime identity or credential leaked")
    return output


def _validate_live_chat(
    root: Path, section: dict[str, Any], thresholds: dict[str, Any]
) -> list[str]:
    path, payload, errors = _artifact(root, section)
    if payload is None:
        return [f"live_chat: {error}" for error in errors]
    rows = payload.get("results") or []
    counts = payload.get("counts") or {}
    required = int(thresholds["chat_cases"])
    output: list[str] = []
    if payload.get("status") != "passed" or int(counts.get("passed") or 0) != required:
        output.append(f"live_chat: passed={counts.get('passed')} expected {required}")
    if len(rows) != required or any(not row.get("passed") for row in rows):
        output.append("live_chat: result rows are incomplete or failed")
    if section.get("must_use_server_default_knowledge_base") and not payload.get(
        "server_default_knowledge_base"
    ):
        output.append("live_chat: server default knowledge base was not used")
    if any(
        not row.get("retrieval_started") or not row.get("retrieval_finished")
        for row in rows
    ):
        output.append("live_chat: retrieval evidence missing")
    if any(str(row.get("terminal_status")) != "SUCCEEDED" for row in rows):
        output.append("live_chat: terminal status is not SUCCEEDED")
    if any(not all(row.get("fact_groups") or []) for row in rows):
        output.append("live_chat: required fact groups missing")
    if any(row.get("forbidden_claims") for row in rows):
        output.append("live_chat: forbidden claims detected")
    if _contains_runtime_identity(path):
        output.append("live_chat: runtime identity or credential leaked")
    return output


def _validate_release(root: Path, section: dict[str, Any]) -> list[str]:
    _, payload, errors = _artifact(root, section)
    if payload is None:
        return [f"release_gate: {error}" for error in errors]
    if section.get("must_pass") and payload.get("overall") != "passed":
        return [f"release_gate: overall={payload.get('overall')} expected passed"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    args = parser.parse_args()
    errors = validate_acceptance(root=args.root, contract_path=args.contract)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("Marketplace QnA acceptance evidence passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
