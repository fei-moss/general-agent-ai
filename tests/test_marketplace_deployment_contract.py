from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_dockerhost_development_exposes_identity_mode_on_api_only():
    env_example = _read("dockerhost/env.example")
    compose = _read("dockerhost/compose.yaml")

    assert "MARKETPLACE_IDENTITY_MODE=legacy-compatible" in env_example
    assert (
        "MARKETPLACE_IDENTITY_MODE: ${MARKETPLACE_IDENTITY_MODE:-legacy-compatible}"
        in compose
    )
    assert compose.count("\n      MARKETPLACE_IDENTITY_MODE:") == 1


def test_api_docs_define_marketplace_headers_reserved_payload_and_legacy_boundary():
    for path in ("docs/API.md", "docs/INTEGRATION_GUIDE.md"):
        document = _read(path)
        for term in (
            "X-Marketplace-User-ID",
            "X-Marketplace-Wallet",
            "marketplace_identity",
            "wallet_address",
            "legacy-compatible",
            "仅限开发",
            "不需要内部服务凭证",
        ):
            assert term in document, f"{path} missing {term}"


def test_production_runbook_requires_private_marketplace_only_chat_boundary():
    runbook = _read("docs/PRODUCTION_READINESS_RUNBOOK.md")

    for term in (
        "MARKETPLACE_IDENTITY_MODE=marketplace",
        "私有网络",
        "禁止公开 Chat ingress",
        "Marketplace-to-Chat 正向 smoke",
        "外部负向可达性 smoke",
        "不引入服务凭证",
    ):
        assert term in runbook, f"production runbook missing {term}"
