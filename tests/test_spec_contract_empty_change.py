from __future__ import annotations

import json
from pathlib import Path
import subprocess


def test_spec_contract_accepts_empty_change_snapshot(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps({"changes": []}), encoding="utf-8")
    artifact_dir = tmp_path / "artifacts"

    completed = subprocess.run(
        ["bash", str(root / "scripts/check_project_spec_contract.sh")],
        cwd=root,
        env={
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "HARNESS_SNAPSHOT_FILE": str(snapshot),
            "HARNESS_ARTIFACT_DIR": str(artifact_dir),
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads((artifact_dir / "spec_contract.json").read_text())
    assert result["status"] == "passed"
    assert result["requires_spec_change"] == 0
    assert result["spec_changed"] == 0


def test_spec_contract_reports_approved_exemption_as_passed(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps({"changes": [{"path": "app/runtime/example.py"}]}),
        encoding="utf-8",
    )
    artifact_dir = tmp_path / "artifacts"

    completed = subprocess.run(
        ["bash", str(root / "scripts/check_project_spec_contract.sh")],
        cwd=root,
        env={
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "HARNESS_SNAPSHOT_FILE": str(snapshot),
            "HARNESS_ARTIFACT_DIR": str(artifact_dir),
            "SPEC_CONTRACT_APPROVED": "1",
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads((artifact_dir / "spec_contract.json").read_text())
    assert result["status"] == "passed"
    assert result["reason"] == "explicit exemption: SPEC_CONTRACT_APPROVED=1"
    assert result["requires_spec_change"] == 1
    assert result["spec_changed"] == 0
