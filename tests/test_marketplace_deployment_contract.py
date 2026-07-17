from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_runtime_and_dockerhost_have_no_chat_identity_mode_switch():
    env_example = _read("dockerhost/env.example")
    compose = _read("dockerhost/compose.yaml")
    config = _read("app/core/config.py")

    assert "MARKETPLACE_IDENTITY_MODE" not in env_example
    assert "MARKETPLACE_IDENTITY_MODE" not in compose
    assert "marketplace_identity_mode" not in config


def test_marketplace_ai_base_url_fails_closed_without_private_override(monkeypatch):
    from app.core.config import Settings

    monkeypatch.delenv("MARKETPLACE_AI_BASE_URL", raising=False)
    settings = Settings(_env_file=None)
    env_example = _read("dockerhost/env.example")
    compose = _read("dockerhost/compose.yaml")
    runbook = _read("docs/PRODUCTION_READINESS_RUNBOOK.md")
    public_dev_url = "app-df-moss-site-agent-marketplace-dev.dkhost.vixmk-yo.org"

    assert settings.marketplace_ai_base_url == ""
    assert public_dev_url not in env_example
    assert public_dev_url not in compose
    assert "MARKETPLACE_AI_BASE_URL: ${MARKETPLACE_AI_BASE_URL:-}" in compose
    assert "MARKETPLACE_AI_BASE_URL=" in env_example
    assert "8081" in env_example
    assert "MARKETPLACE_AI_BASE_URL" in runbook
    assert "8081" in runbook


def test_api_docs_define_one_mandatory_marketplace_identity_contract():
    for path in ("docs/API.md", "docs/INTEGRATION_GUIDE.md"):
        document = _read(path)
        for term in (
            "X-Marketplace-User-ID",
            "X-Marketplace-Wallet",
            "marketplace_identity",
            "wallet_address",
            "所有环境",
            "不需要内部服务凭证",
        ):
            assert term in document, f"{path} missing {term}"
        assert "legacy-compatible" not in document
        assert "MARKETPLACE_IDENTITY_MODE" not in document


def test_production_runbook_requires_private_marketplace_only_chat_boundary():
    runbook = _read("docs/PRODUCTION_READINESS_RUNBOOK.md")

    for term in (
        "私有网络",
        "禁止公开 Chat ingress",
        "Marketplace-to-Chat 正向 smoke",
        "外部负向可达性 smoke",
        "不引入服务凭证",
    ):
        assert term in runbook, f"production runbook missing {term}"
    assert "MARKETPLACE_IDENTITY_MODE" not in runbook
    assert "legacy-compatible" not in runbook


def test_repository_owned_chat_callers_use_marketplace_identity_contract():
    for path in (
        "scripts/dockerhost_release.py",
        "scripts/benchmark_realtime_ttft.py",
        "tests/chat_eval/live_runner.py",
    ):
        source = _read(path)
        for term in (
            "X-Marketplace-User-ID",
            "X-Marketplace-Wallet",
            "marketplace_identity",
        ):
            assert term in source, f"{path} missing {term}"

    assert "X-API-Key" not in _read("scripts/dockerhost_release.py")
    assert "X-API-Key" not in _read("scripts/benchmark_realtime_ttft.py")
    assert '"Authorization": f"Bearer {auth_token}"' not in _read(
        "tests/chat_eval/live_runner.py"
    )

    # `/rag/*` keeps its separate internal-admin contract.
    assert "X-API-Key" in _read("scripts/smoke_rag_pgvector.sh")
