"""Validate the Jenkins/Compose production contract without extra dependencies."""

from __future__ import annotations

import ast
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "ops" / "production-deployment-contract.md"
LEGACY_ROOT_CONTRACT = ROOT / "production-deployment-contract.md"
RUNBOOK = ROOT / "docs" / "DOCKERHOST_RELEASE_RUNBOOK.md"
COMPOSE = ROOT / "docker-compose-prd.yml"
ENV_EXAMPLE = ROOT / ".env.example"
LOCAL_ENV_EXAMPLE = ROOT / "env.local.example"
DOCKERIGNORE = ROOT / ".dockerignore"
GITIGNORE = ROOT / ".gitignore"
DOCKERFILE = ROOT / "dockerhost" / "Dockerfile"
SETTINGS = ROOT / "app" / "core" / "config.py"
AGENTS = ROOT / "AGENTS.md"
README = ROOT / "README.md"

CONTRACT_TERMS = (
    "docker-compose-prd.yml",
    "/data/general-agent-ai",
    "docker compose --env-file .env -f docker-compose-prd.yml up -d --build --remove-orphans",
    "APP_BIND_ADDR",
    "APP_PORT",
    "stdout / stderr",
    "Promtail",
    "Jenkins",
    "dockerhost/",
)

RUNBOOK_TERMS = (
    "SPEC-DOCKERHOST-RELEASE-RUNBOOK-001",
    "envctl check-project",
    "envctl validate-template",
    "--secret-env",
    "--secret-file",
    "/healthz",
    "/readyz",
    "STREAM_FALSE_NOT_SUPPORTED",
    "SSE Smoke",
    "回滚",
    "envctl down",
)

COMPOSE_TERMS = (
    "  api:",
    "  worker:",
    "  reaper:",
    "  migrate:",
    "dockerfile: dockerhost/Dockerfile",
    'restart: unless-stopped',
    'curl -fsS http://localhost:8080/healthz',
    'max-size: "100m"',
    'max-file: "3"',
    '"${APP_BIND_ADDR:?APP_BIND_ADDR is required}:${APP_PORT:-8080}:8080"',
    'condition: service_completed_successfully',
    '"/usr/local/bin/python"',
)

REQUIRED_DOCKERIGNORE = {
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
}

PLACEHOLDER_KEYS = {
    "APP_BIND_ADDR",
    "APP_PORT",
    "DB_URL",
    "REDIS_URL",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
    "LLM_PROVIDER",
    "OPENAI_API_KEY",
    "OPENAI_API_KEY_FILE",
    "OPENAI_MODEL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_API_KEY_FILE",
    "ANTHROPIC_MODEL",
    "QWEN_MODEL",
    "DASHSCOPE_API_KEY",
    "DASHSCOPE_API_KEY_FILE",
    "ZAI_MODEL",
    "ZAI_API_KEY",
    "ZAI_API_KEY_FILE",
    "ZAI_API_KEYS_FILE",
    "GEMINI_MODEL",
    "GEMINI_API_KEY",
    "GEMINI_API_KEY_FILE",
    "LITELLM_MODEL",
    "LITELLM_FALLBACKS",
    "PROVIDER_KEY_POOL_FILE",
    "MARKETPLACE_AI_BASE_URL",
    "RAG_ADMIN_USER_IDS",
    "RAG_DEFAULT_KNOWLEDGE_BASE_ID",
    "RAG_INTERNAL_OWNER_USER_ID",
    "EMBEDDING_PROVIDER",
    "EMBEDDING_MODEL",
    "EMBEDDING_API_KEY",
    "EMBEDDING_API_KEY_FILE",
}

SAFETY_DEFAULTS = {
    "PRODUCTION_MODE": "true",
    "ALLOW_MOCK_PROVIDER": "false",
    "PROVIDER_SECRET_STRICT": "true",
    "PROVIDER_RATE_LIMIT_ENABLED": "true",
    "PROVIDER_RATE_LIMIT_FAIL_OPEN": "false",
}

FORBIDDEN_SECRET_MARKERS = (
    "ENVCTL_TOKEN=",
    "OPENAI_API_KEY=sk-",
    "ZAI_API_KEY=sk-",
    "GEMINI_API_KEY=AIza",
    "-----BEGIN",
)

ENV_LINE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")
COMPOSE_VARIABLE = re.compile(r"\${([A-Z][A-Z0-9_]*)")


def main() -> int:
    failures: list[str] = []

    for path in (
        CONTRACT,
        RUNBOOK,
        COMPOSE,
        ENV_EXAMPLE,
        LOCAL_ENV_EXAMPLE,
        DOCKERIGNORE,
        GITIGNORE,
        DOCKERFILE,
        SETTINGS,
        AGENTS,
        README,
    ):
        if not path.is_file():
            failures.append(f"missing required file: {_relative(path)}")

    if failures:
        return _finish(failures)

    failures.extend(_missing_terms(CONTRACT, CONTRACT_TERMS))
    failures.extend(_missing_terms(RUNBOOK, RUNBOOK_TERMS))
    failures.extend(_missing_terms(COMPOSE, COMPOSE_TERMS))

    if LEGACY_ROOT_CONTRACT.exists():
        failures.append(
            "production-deployment-contract.md must be relocated to "
            "docs/ops/production-deployment-contract.md"
        )

    compose = _read(COMPOSE)
    if compose.count("ports:") != 1:
        failures.append("production compose must publish exactly one service port")
    if compose.count("env_file:") < 4 or compose.count("- .env") < 4:
        failures.append("all production services must load env_file .env")
    if compose.count("restart: unless-stopped") < 3:
        failures.append("api, worker, and reaper must restart unless stopped")
    for forbidden in ('"0.0.0.0:8080:8080"', '"127.0.0.1:8080:8080"'):
        if forbidden in compose:
            failures.append(f"production compose hardcodes forbidden binding: {forbidden}")
    for internal_service in ("  db:", "  cache:"):
        if internal_service in compose:
            failures.append(
                "production state topology is operations-owned; compose must not define "
                f"{internal_service.strip()}"
            )

    env_values, env_errors = _parse_env_example()
    failures.extend(env_errors)
    runtime_keys = _settings_environment_keys()
    compose_keys = set(COMPOSE_VARIABLE.findall(compose))
    required_keys = runtime_keys | compose_keys | {"APP_BIND_ADDR"}
    for key in sorted(required_keys - env_values.keys()):
        failures.append(f".env.example missing required key: {key}")
    allowed_extra = {"APP_BIND_ADDR", "APP_IMAGE_TAG"}
    for key in sorted(env_values.keys() - runtime_keys - compose_keys - allowed_extra):
        failures.append(f".env.example contains unknown key: {key}")
    for key in sorted(PLACEHOLDER_KEYS):
        expected = f"${{{key}}}"
        if env_values.get(key) != expected:
            failures.append(f".env.example must use same-name placeholder for {key}")
    for key, expected in SAFETY_DEFAULTS.items():
        if env_values.get(key) != expected:
            failures.append(f".env.example must set {key}={expected}")

    gitignore = set(_read(GITIGNORE).splitlines())
    for line in sorted({".env", ".env.*", "!.env.example"} - gitignore):
        failures.append(f".gitignore missing required rule: {line}")

    dockerignore = set(_read(DOCKERIGNORE).splitlines())
    for line in sorted(REQUIRED_DOCKERIGNORE - dockerignore):
        failures.append(f".dockerignore missing required rule: {line}")

    dockerfile = _read(DOCKERFILE)
    for forbidden in ("COPY .env", "ADD .env"):
        if forbidden in dockerfile:
            failures.append(f"dockerhost/Dockerfile must not contain {forbidden}")

    agents = _read(AGENTS)
    for term in ("## Mandatory Ops Reference", "docs/ops/production-deployment-contract.md"):
        if term not in agents:
            failures.append(f"AGENTS.md missing required term: {term}")
    if "cp env.local.example .env" not in _read(README):
        failures.append("README local setup must use env.local.example")

    combined = "\n".join(
        _read(path) for path in (CONTRACT, RUNBOOK, COMPOSE, ENV_EXAMPLE, AGENTS)
    )
    for marker in FORBIDDEN_SECRET_MARKERS:
        if marker in combined:
            failures.append(f"forbidden secret-like marker present: {marker}")

    return _finish(failures)


def _parse_env_example() -> tuple[dict[str, str], list[str]]:
    values: dict[str, str] = {}
    failures: list[str] = []
    for line_number, raw_line in enumerate(_read(ENV_EXAMPLE).splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = ENV_LINE.fullmatch(line)
        if not match:
            failures.append(f".env.example:{line_number} is not KEY=value")
            continue
        key, value = match.groups()
        if key in values:
            failures.append(f".env.example duplicates key: {key}")
            continue
        values[key] = value
    return values, failures


def _settings_environment_keys() -> set[str]:
    tree = ast.parse(_read(SETTINGS), filename=str(SETTINGS))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            return {
                item.target.id.upper()
                for item in node.body
                if isinstance(item, ast.AnnAssign)
                and isinstance(item.target, ast.Name)
                and item.value is not None
            }
    return set()


def _missing_terms(path: Path, terms: tuple[str, ...]) -> list[str]:
    text = _read(path)
    return [
        f"{_relative(path)} missing required term: {term}"
        for term in terms
        if term not in text
    ]


def _finish(failures: list[str]) -> int:
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS production deployment contract")
    return 0


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
