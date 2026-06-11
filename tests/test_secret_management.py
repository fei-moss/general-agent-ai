from __future__ import annotations

from app.core.config import Settings
from app.core.secrets import (
    ProviderSecretMissingError,
    SecretValue,
    build_secret_provider,
    redact_secret,
)
from app.runtime.agent_factory import build_model


def test_mock_provider_requires_no_secret():
    provider = build_secret_provider(Settings(_env_file=None, llm_provider="mock"))

    provider.validate_required("mock", "mock")


def test_real_provider_missing_secret_fails_fast_with_sanitized_error():
    provider = build_secret_provider(Settings(_env_file=None, llm_provider="openai"))

    try:
        provider.validate_required("openai", "gpt-test")
    except ProviderSecretMissingError as exc:
        message = str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ProviderSecretMissingError")

    assert "PROVIDER_SECRET_MISSING" in message
    assert "sk-" not in message


def test_file_injected_secret_is_loaded(tmp_path):
    path = tmp_path / "openai_api_key"
    path.write_text("sk-file-secret\n", encoding="utf-8")
    provider = build_secret_provider(
        Settings(_env_file=None, llm_provider="openai", openai_api_key_file=str(path))
    )

    secret = provider.get_secret("openai_api_key")

    assert secret is not None
    assert secret.reveal() == "sk-file-secret"
    assert "sk-file-secret" not in repr(secret)
    assert "sk-file-secret" not in str(secret)


def test_secret_values_are_redacted_from_application_errors():
    text = "provider failed with key sk-real-secret"

    assert redact_secret(text, [SecretValue("sk-real-secret")]) == (
        "provider failed with key ********"
    )


def test_agent_factory_does_not_use_not_set_api_key_for_real_provider():
    try:
        build_model(Settings(_env_file=None, llm_provider="openai", openai_api_key=""))
    except Exception as exc:
        message = str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected missing secret failure")

    assert "PROVIDER_SECRET_MISSING" in message
    assert "not-set" not in message


def test_legacy_openai_provider_reads_file_injected_secret(tmp_path):
    from app.llm.providers import OpenAICompatProvider

    path = tmp_path / "openai_api_key"
    path.write_text("sk-file-legacy\n", encoding="utf-8")
    provider = OpenAICompatProvider(
        Settings(_env_file=None, openai_api_key="", openai_api_key_file=str(path))
    )

    headers = provider._headers()

    assert headers["Authorization"] == "Bearer sk-file-legacy"
