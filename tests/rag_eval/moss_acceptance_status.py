from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tests.rag_eval.moss_acceptance_validator import (
    DEFAULT_CONTRACT_PATH,
    REPO_ROOT,
    validate_acceptance,
)


DEFAULT_OUTPUT = Path(".artifacts/release/moss_rag_acceptance_status.json")


def build_acceptance_status(
    *,
    root: Path = REPO_ROOT,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    """Build a non-authoritative status report from the acceptance validator."""
    contract = _load_json(contract_path)
    blockers = validate_acceptance(root=root, contract_path=contract_path)
    return {
        "contract_id": contract["contract_id"],
        "status": "passed" if not blockers else "blocked",
        "blockers": blockers,
        "artifacts": {
            "baseline_eval": _promptfoo_artifact_status(root, contract["baseline_eval"]),
            "gemini_preflight": _json_artifact_status(
                root,
                contract["gemini_preflight"]["artifact_path"],
                status_field="status",
            ),
            "semantic_eval": _promptfoo_artifact_status(root, contract["semantic_eval"]),
            "persistent_ingestion_payload": _jsonl_artifact_status(
                root,
                contract["persistent_ingestion"]["payload_artifact_path"],
            ),
            "persistent_ingestion_summary": _json_artifact_status(
                root,
                contract["persistent_ingestion"]["summary_artifact_path"],
                status_field=None,
            ),
            "release_gate": _json_artifact_status(
                root,
                contract["release_gate"]["artifact_path"],
                status_field="overall",
            ),
        },
        "next_commands": [
            contract["gemini_preflight"]["command"],
            (
                "PROMPTFOO_PYTHON=.venv/bin/python npx --yes promptfoo@latest eval "
                "-c tests/rag_eval/moss_promptfooconfig.yaml --no-cache "
                "--output .artifacts/release/moss_rag_promptfoo_eval.json"
            ),
            (
                ".venv/bin/python -m tests.rag_eval.moss_import_payloads "
                "--knowledge-base-id <knowledge_base_id> "
                "> .artifacts/release/moss_rag_document_payloads.jsonl"
            ),
            ".venv/bin/python -m tests.rag_eval.moss_acceptance_validator",
        ],
    }


def write_acceptance_status(
    *,
    output_path: Path = DEFAULT_OUTPUT,
    root: Path = REPO_ROOT,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    status = build_acceptance_status(root=root, contract_path=contract_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return status


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write a machine-readable MOSS RAG acceptance status report."
    )
    parser.add_argument("--root", default=str(REPO_ROOT))
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    status = write_acceptance_status(
        output_path=Path(args.output),
        root=Path(args.root),
        contract_path=Path(args.contract),
    )
    print(f"MOSS acceptance status {status['status']} -> {args.output}")
    if status["status"] != "passed":
        raise SystemExit(1)


def _promptfoo_artifact_status(root: Path, section: dict[str, Any]) -> dict[str, Any]:
    path = root / section["artifact_path"]
    base = {"path": section["artifact_path"], "status": "missing", "exists": path.exists()}
    if not path.exists():
        return base
    try:
        payload = _load_json(path)
        stats = payload["results"]["stats"]
        successes = int(stats.get("successes") or 0)
        failures = int(stats.get("failures") or 0)
        errors = int(stats.get("errors") or 0)
    except Exception as exc:  # noqa: BLE001 - status report surfaces shape problems
        return {**base, "status": "invalid", "error": str(exc)}

    total = successes + failures + errors
    return {
        **base,
        "status": "passed" if total and failures == 0 and errors == 0 else "failed",
        "successes": successes,
        "failures": failures,
        "errors": errors,
        "total": total,
    }


def _json_artifact_status(
    root: Path,
    artifact_path: str,
    *,
    status_field: str | None,
) -> dict[str, Any]:
    path = root / artifact_path
    base = {"path": artifact_path, "status": "missing", "exists": path.exists()}
    if not path.exists():
        return base
    try:
        payload = _load_json(path)
    except Exception as exc:  # noqa: BLE001
        return {**base, "status": "invalid", "error": str(exc)}
    status = payload.get(status_field) if status_field else "present"
    result = {**base, "status": status}
    for field in ["http_status", "reason", "caller_ip", "embedding_model", "submitted_documents", "succeeded_jobs", "failed_jobs"]:
        if field in payload:
            result[field] = payload[field]
    return result


def _jsonl_artifact_status(root: Path, artifact_path: str) -> dict[str, Any]:
    path = root / artifact_path
    base = {"path": artifact_path, "status": "missing", "exists": path.exists()}
    if not path.exists():
        return base
    row_count = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return {**base, "status": "present", "row_count": row_count}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
