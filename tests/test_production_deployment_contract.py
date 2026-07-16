from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "production-deployment-contract.md"
CHECKER = ROOT / "scripts/check_production_deployment_contract.py"
PROFILE = ROOT / "harness/harness_profiles.json"
PROJECT_RELEASE = ROOT / "scripts/check_project_release.sh"


def test_root_production_deployment_contract_exists_and_names_gates():
    text = CONTRACT.read_text(encoding="utf-8")

    for term in (
        "SPEC-PLATFORM-MECHANISM-ABSORPTION-002",
        "DockerHost Git pull deployment",
        "envctl check-project",
        "envctl validate-template",
        "--secret-env",
        "/healthz",
        "/readyz",
        "SSE smoke",
        "rollback",
        "envctl down",
        "gitleaks",
    ):
        assert term in text


def test_production_deployment_contract_checker_passes():
    from scripts.check_production_deployment_contract import main

    assert main() == 0


def test_release_profile_runs_production_deployment_contract_checker():
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    text = PROJECT_RELEASE.read_text(encoding="utf-8")

    assert profile["custom_gates"]["project_release"]["run"] == "scripts/check_project_release.sh"
    assert "project_release" in profile["gate_sets"]["release"]
    assert "production_deployment_contract" in text
    assert "check_production_deployment_contract.py" in text
