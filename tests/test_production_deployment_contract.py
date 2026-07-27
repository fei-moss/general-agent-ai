from __future__ import annotations

import json
from pathlib import Path

from app.core.config import Settings


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "ops" / "production-deployment-contract.md"
COMPOSE = ROOT / "docker-compose-prd.yml"
ENV_EXAMPLE = ROOT / ".env.example"
LOCAL_ENV_EXAMPLE = ROOT / "env.local.example"
DOCKERIGNORE = ROOT / ".dockerignore"
GITIGNORE = ROOT / ".gitignore"
DOCKERFILE = ROOT / "dockerhost" / "Dockerfile"
AGENTS = ROOT / "AGENTS.md"
README = ROOT / "README.md"
CHECKER = ROOT / "scripts" / "check_production_deployment_contract.py"
PROFILE = ROOT / "harness" / "harness_profiles.json"
PROJECT_RELEASE = ROOT / "scripts" / "check_project_release.sh"


def _env_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        assert separator, raw_line
        assert key not in values, f"duplicate environment key: {key}"
        values[key] = value
    return values


def test_production_contract_is_relocated_and_agent_guidance_points_to_it():
    assert CONTRACT.is_file()
    assert not (ROOT / "production-deployment-contract.md").exists()

    text = CONTRACT.read_text(encoding="utf-8")
    for term in (
        "docker-compose-prd.yml",
        "/data/general-agent-ai",
        "docker compose --env-file .env -f docker-compose-prd.yml up -d --build --remove-orphans",
        "APP_BIND_ADDR",
        "APP_PORT",
        "stdout / stderr",
        "Promtail",
        "Jenkins",
        "dockerhost/",
    ):
        assert term in text

    guidance = AGENTS.read_text(encoding="utf-8")
    assert "## Mandatory Ops Reference" in guidance
    assert "docs/ops/production-deployment-contract.md" in guidance


def test_production_compose_has_stable_services_and_only_api_host_binding():
    text = COMPOSE.read_text(encoding="utf-8")

    for service in ("api", "worker", "reaper", "migrate"):
        assert f"  {service}:" in text
    assert "  db:" not in text
    assert "  cache:" not in text
    assert text.count("restart: unless-stopped") >= 3
    assert text.count("env_file:") >= 4
    assert text.count("- .env") >= 4
    assert (
        '"${APP_BIND_ADDR:?APP_BIND_ADDR is required}:${APP_PORT:-8080}:8080"'
        in text
    )
    assert text.count("ports:") == 1
    assert '"0.0.0.0:8080:8080"' not in text
    assert '"127.0.0.1:8080:8080"' not in text
    assert "curl -fsS http://localhost:8080/healthz" in text
    assert 'max-size: "100m"' in text
    assert 'max-file: "3"' in text
    assert "dockerfile: dockerhost/Dockerfile" in text


def test_production_env_covers_runtime_and_compose_with_sensitive_placeholders():
    values = _env_values()
    expected_runtime = {name.upper() for name in Settings.model_fields}
    assert not (expected_runtime - values.keys())

    for key in (
        "APP_BIND_ADDR",
        "APP_PORT",
        "DB_URL",
        "REDIS_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
        "OPENAI_API_KEY",
        "OPENAI_API_KEY_FILE",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_API_KEY_FILE",
        "DASHSCOPE_API_KEY",
        "DASHSCOPE_API_KEY_FILE",
        "ZAI_API_KEY",
        "ZAI_API_KEY_FILE",
        "ZAI_API_KEYS_FILE",
        "GEMINI_API_KEY",
        "GEMINI_API_KEY_FILE",
        "EMBEDDING_API_KEY",
        "EMBEDDING_API_KEY_FILE",
        "PROVIDER_KEY_POOL_FILE",
        "MARKETPLACE_AI_BASE_URL",
        "RAG_ADMIN_USER_IDS",
        "RAG_DEFAULT_KNOWLEDGE_BASE_ID",
        "RAG_INTERNAL_OWNER_USER_ID",
    ):
        assert values[key] == f"${{{key}}}"

    assert values["PRODUCTION_MODE"] == "true"
    assert values["ALLOW_MOCK_PROVIDER"] == "false"
    assert values["PROVIDER_SECRET_STRICT"] == "true"
    assert values["PROVIDER_RATE_LIMIT_FAIL_OPEN"] == "false"


def test_real_env_and_build_context_are_ignored_without_hiding_templates():
    gitignore = set(GITIGNORE.read_text(encoding="utf-8").splitlines())
    assert {".env", ".env.*", "!.env.example"} <= gitignore

    dockerignore = set(DOCKERIGNORE.read_text(encoding="utf-8").splitlines())
    assert {
        ".git",
        ".env",
        ".env.*",
        "!.env.example",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        "dist",
        "build",
        "*.tar.gz",
    } <= dockerignore

    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert "COPY .env" not in dockerfile
    assert "ADD .env" not in dockerfile
    assert LOCAL_ENV_EXAMPLE.is_file()
    assert "cp env.local.example .env" in README.read_text(encoding="utf-8")


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
    assert '"status": "passed"' in text
    assert '"status": "failed"' in text
    assert '"overall":' not in text
