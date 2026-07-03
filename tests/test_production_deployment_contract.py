from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "production-deployment-contract.md"
CHECKER = ROOT / "scripts/check_production_deployment_contract.py"
VERIFY = ROOT / "scripts/verify_release.sh"


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


def test_verify_release_runs_production_deployment_contract_checker():
    text = VERIFY.read_text(encoding="utf-8")

    assert "production_deployment_contract" in text
    assert "check_production_deployment_contract.py" in text
