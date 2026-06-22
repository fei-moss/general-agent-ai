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


def test_zai_file_injected_secret_is_loaded(tmp_path):
    path = tmp_path / "zai_api_key"
    path.write_text("zai-file-secret\n", encoding="utf-8")
    provider = build_secret_provider(
        Settings(_env_file=None, llm_provider="zai", zai_api_key_file=str(path))
    )

    secret = provider.get_secret("zai_api_key")

    assert secret is not None
    assert secret.reveal() == "zai-file-secret"
    provider.validate_required("zai", "glm-5.2")


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


def test_agent_factory_zai_missing_secret_fails_fast():
    try:
        build_model(Settings(_env_file=None, llm_provider="zai", zai_api_key=""))
    except Exception as exc:
        message = str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected missing secret failure")

    assert "PROVIDER_SECRET_MISSING" in message
    assert "zai" in message
    assert "zai-file-secret" not in message


def test_legacy_openai_provider_reads_file_injected_secret(tmp_path):
    from app.llm.providers import OpenAICompatProvider

    path = tmp_path / "openai_api_key"
    path.write_text("sk-file-legacy\n", encoding="utf-8")
    provider = OpenAICompatProvider(
        Settings(_env_file=None, openai_api_key="", openai_api_key_file=str(path))
    )

    headers = provider._headers()

    assert headers["Authorization"] == "Bearer sk-file-legacy"


def test_legacy_zai_provider_headers_and_payload_use_zai_settings():
    from app.llm.providers import ZAICompatProvider

    provider = ZAICompatProvider(
        Settings(
            _env_file=None,
            zai_api_key="zai-inline-secret",
            provider_default_max_output_tokens=2048,
        )
    )

    headers = provider._headers()
    payload = provider._payload(
        [{"role": "user", "content": "hello"}],
        stream=True,
        context="mock-only context",
        thinking_type="disabled",
        reasoning_effort="low",
    )

    assert headers["Authorization"] == "Bearer zai-inline-secret"
    assert payload == {
        "model": "glm-5.2",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": True,
        "max_tokens": 2048,
        "tool_stream": True,
        "thinking": {"type": "disabled"},
        "reasoning_effort": "low",
    }
