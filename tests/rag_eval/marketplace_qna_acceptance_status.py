"""Write a concise Marketplace QnA acceptance handoff artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tests.rag_eval.marketplace_qna_acceptance_validator import (
    DEFAULT_CONTRACT_PATH,
    REPO_ROOT,
    validate_acceptance,
)


DEFAULT_OUTPUT = Path(".artifacts/release/marketplace_qna_acceptance_status.json")


def build_acceptance_status(
    *, root: Path = REPO_ROOT, contract_path: Path = DEFAULT_CONTRACT_PATH
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    blockers = validate_acceptance(root=root, contract_path=contract_path)
    artifacts: dict[str, Any] = {}
    for name, section in contract.items():
        if not isinstance(section, dict):
            continue
        artifact_path = section.get("artifact_path") or section.get(
            "summary_artifact_path"
        )
        if artifact_path:
            artifacts[name] = {
                "path": artifact_path,
                "exists": (root / artifact_path).exists(),
            }
    return {
        "contract_id": contract["contract_id"],
        "status": "passed" if not blockers else "blocked",
        "blockers": blockers,
        "artifacts": artifacts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_acceptance_status(root=args.root, contract_path=args.contract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Marketplace QnA acceptance status {report['status']} -> {args.output}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
