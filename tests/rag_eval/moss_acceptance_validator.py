from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parents[1]
DEFAULT_CONTRACT_PATH = EVAL_DIR / "moss_acceptance_evidence_contract.json"


def validate_acceptance(
    *,
    root: Path = REPO_ROOT,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
) -> list[str]:
    """Validate final MOSS RAG acceptance artifacts against the evidence contract."""
    contract = _load_json(contract_path)
    errors: list[str] = []
    errors.extend(_validate_promptfoo_eval(root, contract["baseline_eval"], "baseline_eval"))
    errors.extend(_validate_gemini_preflight(root, contract["gemini_preflight"]))
    errors.extend(_validate_promptfoo_eval(root, contract["semantic_eval"], "semantic_eval"))
    errors.extend(_validate_ingestion(root, contract))
    errors.extend(_validate_release_gate(root, contract["release_gate"]))
    return errors


def _validate_promptfoo_eval(
    root: Path,
    section: dict[str, Any],
    label: str,
) -> list[str]:
    path = root / section["artifact_path"]
    if not path.exists():
        return [f"{label}: missing artifact {section['artifact_path']}"]
    try:
        payload = _load_json(path)
        result_block = payload["results"]
        stats = result_block["stats"]
        results = result_block["results"]
    except Exception as exc:  # noqa: BLE001 - validator reports data-shape errors
        return [f"{label}: invalid Promptfoo artifact shape: {exc}"]

    errors: list[str] = []
    expected_count = int(section["expected_case_count"])
    successes = int(stats.get("successes") or 0)
    failures = int(stats.get("failures") or 0)
    errors_count = int(stats.get("errors") or 0)
    total = successes + failures + errors_count
    pass_rate = successes / total if total else 0.0

    if len(results) != expected_count:
        errors.append(f"{label}: expected {expected_count} result rows, got {len(results)}")
    if total != expected_count:
        errors.append(f"{label}: expected {expected_count} total cases, got {total}")
    if failures or errors_count:
        errors.append(f"{label}: failures={failures}, errors={errors_count}")
    if pass_rate < float(section["required_pass_rate"]):
        errors.append(
            f"{label}: pass_rate={pass_rate:.4f} below {section['required_pass_rate']}"
        )
    return errors


def _validate_ingestion(root: Path, contract: dict[str, Any]) -> list[str]:
    section = contract["persistent_ingestion"]
    errors: list[str] = []
    payload_path = root / section["payload_artifact_path"]
    summary_path = root / section["summary_artifact_path"]
    if not payload_path.exists():
        errors.append(f"persistent_ingestion: missing payload artifact {payload_path}")
    else:
        payload_rows = _load_jsonl(payload_path)
        if len(payload_rows) != int(section["expected_document_count"]):
            errors.append(
                "persistent_ingestion: expected "
                f"{section['expected_document_count']} payload rows, got {len(payload_rows)}"
            )

    if not summary_path.exists():
        errors.append(f"persistent_ingestion: missing summary artifact {summary_path}")
        return errors

    try:
        summary = _load_json(summary_path)
    except Exception as exc:  # noqa: BLE001
        return [*errors, f"persistent_ingestion: invalid summary json: {exc}"]

    if int(summary.get("submitted_documents") or 0) != int(section["expected_document_count"]):
        errors.append("persistent_ingestion: submitted_documents count mismatch")
    if int(summary.get("succeeded_jobs") or 0) != int(section["required_succeeded_jobs"]):
        errors.append("persistent_ingestion: succeeded_jobs count mismatch")
    if int(summary.get("failed_jobs") or 0) != 0:
        errors.append("persistent_ingestion: failed_jobs must be 0")

    smoke = summary.get("smoke_query") or {}
    expected_smoke = contract["smoke_query"]
    if bool(smoke.get("degraded")) != bool(expected_smoke["must_be_degraded"]):
        errors.append("smoke_query: degraded state mismatch")
    matched_doc_ids = set(smoke.get("matched_doc_ids") or [])
    expected_doc_ids = set(expected_smoke["expected_doc_ids"])
    if not expected_doc_ids <= matched_doc_ids:
        errors.append(
            "smoke_query: missing expected doc ids "
            f"{sorted(expected_doc_ids - matched_doc_ids)}"
        )
    return errors


def _validate_gemini_preflight(root: Path, section: dict[str, Any]) -> list[str]:
    path = root / section["artifact_path"]
    if not path.exists():
        return [f"gemini_preflight: missing artifact {section['artifact_path']}"]
    try:
        payload = _load_json(path)
    except Exception as exc:  # noqa: BLE001
        return [f"gemini_preflight: invalid preflight json: {exc}"]

    errors: list[str] = []
    required_status = section["required_status"]
    if payload.get("status") != required_status:
        errors.append(
            f"gemini_preflight: status={payload.get('status')} expected {required_status}"
        )
    if payload.get("embedding_model") != section["embedding_model"]:
        errors.append("gemini_preflight: embedding_model mismatch")
    if payload.get("status") == "passed" and int(payload.get("embedding_dimension") or 0) != int(
        section["embedding_dimension"]
    ):
        errors.append("gemini_preflight: embedding_dimension mismatch")
    return errors


def _validate_release_gate(root: Path, section: dict[str, Any]) -> list[str]:
    path = root / section["artifact_path"]
    if not path.exists():
        return [f"release_gate: missing artifact {section['artifact_path']}"]
    try:
        payload = _load_json(path)
    except Exception as exc:  # noqa: BLE001
        return [f"release_gate: invalid summary json: {exc}"]
    if section.get("must_pass") and payload.get("overall") != "passed":
        return [f"release_gate: expected overall=passed, got {payload.get('overall')}"]
    return []


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate final MOSS RAG acceptance artifacts."
    )
    parser.add_argument("--root", default=str(REPO_ROOT))
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT_PATH))
    args = parser.parse_args()
    errors = validate_acceptance(root=Path(args.root), contract_path=Path(args.contract))
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)
    print("MOSS RAG acceptance evidence passed")


if __name__ == "__main__":
    main()
