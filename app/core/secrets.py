"""Secret loading and redaction helpers for LLM providers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import Settings


class ProviderSecretMissingError(RuntimeError):
    """Raised when a real provider is selected without its required secret."""


@dataclass(frozen=True)
class SecretValue:
    """In-memory secret wrapper whose string representation is always redacted."""

    _value: str

    def reveal(self) -> str:
        return self._value

    def __bool__(self) -> bool:
        return bool(self._value)

    def __repr__(self) -> str:
        return "SecretValue(********)"

    def __str__(self) -> str:
        return "********"


class SecretProvider(Protocol):
    def get_secret(self, name: str) -> SecretValue | None:
        """Return a secret by logical lowercase name, or None."""
        ...

    def validate_required(self, provider: str, model: str | None = None) -> None:
        """Raise a sanitized error if provider needs a missing secret."""
        ...


def is_mock_provider(provider: str | None) -> bool:
    """Return whether a provider name should bypass real-provider guardrails."""
    return (provider or "mock").strip().lower() in {"", "mock", "function", "offline"}


def required_secret_name(provider: str | None) -> str | None:
    """Map a canonical provider to the logical secret name used by this app."""
    key = (provider or "mock").strip().lower()
    if is_mock_provider(key):
        return None
    if key == "qwen":
        return "dashscope_api_key"
    if key in {"openai", "anthropic", "gemini", "dashscope", "zai"}:
        return f"{key}_api_key"
    return f"{key}_api_key"


class SettingsSecretProvider:
    """Read secrets from Settings fields and optional mounted secret files."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_secret(self, name: str) -> SecretValue | None:
        normalized = name.strip().lower()
        value = self._read_file_secret(normalized)
        if value is None:
            value = getattr(self._settings, normalized, "")
        if not value:
            return None
        return SecretValue(str(value).strip())

    def validate_required(self, provider: str, model: str | None = None) -> None:
        if is_mock_provider(provider):
            return
        secret_name = required_secret_name(provider)
        if secret_name and self.get_secret(secret_name):
            return
        label = f"{provider}/{model}" if model else provider
        raise ProviderSecretMissingError(
            f"PROVIDER_SECRET_MISSING provider={label} secret={secret_name}"
        )

    def _read_file_secret(self, name: str) -> str | None:
        file_attr = f"{name}_file"
        path = getattr(self._settings, file_attr, "")
        if not path:
            return None
        try:
            return Path(path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ProviderSecretMissingError(
                f"PROVIDER_SECRET_MISSING secret={name} source={file_attr}"
            ) from exc


def build_secret_provider(settings: Settings) -> SettingsSecretProvider:
    """Build the application secret provider from deployment-injected settings."""
    return SettingsSecretProvider(settings)


def redact_secret(text: str, secrets: list[SecretValue | str | None]) -> str:
    """Best-effort redaction for application-authored error strings."""
    redacted = text
    for secret in secrets:
        if secret is None:
            continue
        value = secret.reveal() if isinstance(secret, SecretValue) else str(secret)
        if value:
            redacted = redacted.replace(value, "********")
    return redacted
