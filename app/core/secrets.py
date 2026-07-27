"""Secret loading and redaction helpers for LLM providers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Protocol

from app.core.config import Settings, get_settings


_CREDENTIAL_URL_RE = re.compile(
    r"(?P<prefix>[a-zA-Z][a-zA-Z0-9+.-]*://[^:/\s]+:)[^@\s/]+@"
)
_BEARER_RE = re.compile(r"(?i)Bearer\s+[A-Za-z0-9._~+/-]+=*")
_OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{6,}\b")
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:TOKEN|SECRET|KEY|PASSWORD)[A-Z0-9_]*)"
    r"\s*[:=]\s*([^\s,\"']+)"
)


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

    def redact(self, text: str) -> str:
        """Redact every provider secret observed by this process."""
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
        self._known_secrets: list[SecretValue] = []

    def get_secret(self, name: str) -> SecretValue | None:
        normalized = name.strip().lower()
        value = self._read_file_secret(normalized)
        if value is None:
            value = getattr(self._settings, normalized, "")
        if not value:
            return None
        secret = SecretValue(str(value).strip())
        self.register_secret(secret)
        return secret

    def register_secret(self, secret: SecretValue | str | None) -> None:
        if secret is None:
            return
        value = secret if isinstance(secret, SecretValue) else SecretValue(str(secret))
        if not value.reveal() or any(
            known.reveal() == value.reveal() for known in self._known_secrets
        ):
            return
        self._known_secrets.append(value)

    def redact(self, text: str) -> str:
        direct = [
            getattr(self._settings, name, "")
            for name in (
                "openai_api_key",
                "anthropic_api_key",
                "gemini_api_key",
                "dashscope_api_key",
                "zai_api_key",
                "embedding_api_key",
            )
        ]
        return redact_secret(text, [*self._known_secrets, *direct])

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


def redact_runtime_error(
    text: str,
    provider: SecretProvider | None = None,
    settings: Settings | None = None,
) -> str:
    """Sanitize an exception before it reaches logs, storage, or event streams."""
    try:
        active = provider or build_secret_provider(settings or get_settings())
        redact = getattr(active, "redact", None)
        redacted = redact(text) if callable(redact) else text
        redacted = _CREDENTIAL_URL_RE.sub(r"\g<prefix>********@", redacted)
        redacted = _BEARER_RE.sub("Bearer ********", redacted)
        redacted = _OPENAI_KEY_RE.sub("sk-********", redacted)
        redacted = _SENSITIVE_ASSIGNMENT_RE.sub(r"\1=********", redacted)
        return redacted
    except Exception:
        return "internal error"
