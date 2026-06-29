"""Provider/model global rate limiting and usage settlement."""

from __future__ import annotations

import asyncio
import json
import math
import re
import time
from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import Settings
from app.core.metrics import Metrics
from app.core.secrets import is_mock_provider

ProviderLimitReason = Literal[
    "ALLOWED",
    "RATE_LIMITED",
    "BACKING_OFF",
    "CONFIG_MISSING",
    "UNAVAILABLE",
]


class ProviderRateLimitError(RuntimeError):
    """Raised when a model call cannot proceed under provider quota."""

    def __init__(
        self,
        reason: ProviderLimitReason,
        *,
        retry_after_ms: int | None = None,
    ) -> None:
        self.reason = reason
        self.retry_after_ms = retry_after_ms
        super().__init__(reason)


@dataclass(frozen=True)
class ProviderIdentity:
    provider: str
    model: str
    mock: bool = False

    @property
    def key(self) -> str:
        return provider_key(self.provider, self.model)


@dataclass(frozen=True)
class ProviderLimitConfig:
    rpm: int
    tpm: int

    def __post_init__(self) -> None:
        if self.rpm <= 0 or self.tpm <= 0:
            raise ValueError("provider limit rpm/tpm must be positive")


@dataclass(frozen=True)
class ProviderLimitRequest:
    provider: str
    model: str
    estimated_input_tokens: int
    max_output_tokens: int
    route_type: str
    agent_run_id: str | None = None
    user_id: str | None = None

    @property
    def reserved_tokens(self) -> int:
        return max(0, self.estimated_input_tokens) + max(0, self.max_output_tokens)


@dataclass(frozen=True)
class ProviderLimitDecision:
    allowed: bool
    reason: ProviderLimitReason
    retry_after_ms: int | None = None
    provider_limit_key: str | None = None
    reserved_tokens: int = 0
    remaining_rpm: float | None = None
    remaining_tpm: float | None = None


@dataclass(frozen=True)
class ProviderUsageSettlement:
    provider: str
    model: str
    reserved_tokens: int
    actual_input_tokens: int | None
    actual_output_tokens: int | None
    route_type: str
    agent_run_id: str | None = None

    @property
    def actual_total_tokens(self) -> int | None:
        if self.actual_input_tokens is None or self.actual_output_tokens is None:
            return None
        return max(0, self.actual_input_tokens) + max(0, self.actual_output_tokens)


@dataclass(frozen=True)
class ProviderUsageDecision:
    settled: bool
    usage_missing: bool = False
    debit_tokens: int = 0
    remaining_tpm: float | None = None


_SAFE_KEY_RE = re.compile(r"[^a-z0-9_.:-]+")


def canonical_name(value: str) -> str:
    normalized = _SAFE_KEY_RE.sub("-", value.strip().lower()).strip("-")
    return normalized or "unknown"


def provider_key(provider: str, model: str) -> str:
    return f"ratelimit:provider:{canonical_name(provider)}:{canonical_name(model)}"


def provider_backoff_key(provider: str, model: str) -> str:
    return f"backoff:provider:{canonical_name(provider)}:{canonical_name(model)}"


def provider_identity_from_settings(settings: Settings) -> ProviderIdentity:
    provider = (getattr(settings, "llm_provider", "mock") or "mock").strip().lower()
    if is_mock_provider(provider):
        return ProviderIdentity("mock", "mock", mock=True)
    model = {
        "openai": getattr(settings, "openai_model", "openai"),
        "qwen": getattr(settings, "qwen_model", "qwen"),
        "zai": getattr(settings, "zai_model", "glm-5.2"),
        "anthropic": getattr(settings, "anthropic_model", "anthropic"),
        "gemini": getattr(settings, "gemini_model", "gemini"),
    }.get(provider, provider)
    return ProviderIdentity(canonical_name(provider), canonical_name(model), mock=False)


def estimate_input_tokens(text: str) -> int:
    """Cheap conservative-ish estimate for admission before provider usage exists."""
    return max(1, math.ceil(len(text or "") / 3))


def load_provider_limit_config(settings: Settings) -> dict[tuple[str, str], ProviderLimitConfig]:
    raw = getattr(settings, "provider_rate_limits_json", "{}") or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid provider_rate_limits_json") from exc
    configs: dict[tuple[str, str], ProviderLimitConfig] = {}
    if not isinstance(parsed, dict):
        raise ValueError("provider_rate_limits_json must be an object")
    for key, value in parsed.items():
        if not isinstance(value, dict):
            raise ValueError("provider limit entry must be an object")
        provider, _, model = str(key).partition(":")
        if not model:
            provider, _, model = str(key).partition("/")
        if not model:
            raise ValueError("provider limit key must be provider:model")
        configs[(canonical_name(provider), canonical_name(model))] = ProviderLimitConfig(
            rpm=int(value.get("rpm", getattr(settings, "provider_default_rpm", 100000))),
            tpm=int(value.get("tpm", getattr(settings, "provider_default_tpm", 1000000))),
        )
    return configs


class InMemoryProviderRateLimiter:
    """Deterministic limiter used by tests and as a local no-Redis fallback."""

    def __init__(
        self,
        configs: dict[tuple[str, str], ProviderLimitConfig] | None = None,
        *,
        default_config: ProviderLimitConfig | None = None,
        metrics: Metrics | None = None,
        now_ms: Any | None = None,
    ) -> None:
        self._configs = configs or {}
        self._default = default_config or ProviderLimitConfig(rpm=100000, tpm=1000000)
        self._metrics = metrics or Metrics()
        self._now_ms = now_ms or (lambda: int(time.time() * 1000))
        self._buckets: dict[str, dict[str, float]] = {}
        self._backoff_until: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def check(self, request: ProviderLimitRequest) -> ProviderLimitDecision:
        async with self._lock:
            return self._acquire_locked(request, reserve=False)

    async def acquire(self, request: ProviderLimitRequest) -> ProviderLimitDecision:
        async with self._lock:
            return self._acquire_locked(request, reserve=True)

    async def settle_usage(self, settlement: ProviderUsageSettlement) -> ProviderUsageDecision:
        actual = settlement.actual_total_tokens
        labels = {
            "provider": canonical_name(settlement.provider),
            "model": canonical_name(settlement.model),
            "route_type": settlement.route_type,
        }
        if actual is None:
            self._metrics.inc_counter("provider_usage_missing_total", labels)
            return ProviderUsageDecision(settled=False, usage_missing=True)
        debit = max(0, actual - max(0, settlement.reserved_tokens))
        async with self._lock:
            key = provider_key(settlement.provider, settlement.model)
            cfg = self._config_for(settlement.provider, settlement.model)
            bucket = self._bucket(key, cfg)
            self._refill(bucket, cfg)
            if debit:
                bucket["tpm_tokens"] -= debit
        self._metrics.inc_counter(
            "provider_rate_limit_tokens_settled_total", labels, actual
        )
        if debit:
            self._metrics.inc_counter(
                "provider_rate_limit_tokens_debt_total", labels, debit
            )
        return ProviderUsageDecision(
            settled=True,
            debit_tokens=debit,
            remaining_tpm=bucket["tpm_tokens"],
        )

    async def record_provider_error(
        self,
        provider: str,
        model: str,
        status_code: int,
        retry_after_ms: int | None = None,
    ) -> None:
        if status_code < 429:
            return
        retry_after_ms = retry_after_ms or (30000 if status_code == 429 else 5000)
        self._backoff_until[provider_backoff_key(provider, model)] = (
            self._now_ms() + retry_after_ms
        )
        self._metrics.inc_counter(
            "provider_errors_total",
            {
                "provider": canonical_name(provider),
                "model": canonical_name(model),
                "status_code": str(status_code),
            },
        )

    def _acquire_locked(
        self, request: ProviderLimitRequest, *, reserve: bool
    ) -> ProviderLimitDecision:
        cfg = self._config_for(request.provider, request.model)
        key = provider_key(request.provider, request.model)
        backoff = self._retry_after_backoff_ms(request.provider, request.model)
        if backoff > 0:
            return self._decision(request, False, "BACKING_OFF", backoff, key)
        bucket = self._bucket(key, cfg)
        self._refill(bucket, cfg)
        need_rpm = 1
        need_tpm = max(1, request.reserved_tokens)
        rpm_wait = self._wait_ms(bucket["rpm_tokens"], need_rpm, cfg.rpm)
        tpm_wait = self._wait_ms(bucket["tpm_tokens"], need_tpm, cfg.tpm)
        retry_after = max(rpm_wait, tpm_wait)
        if retry_after > 0:
            return self._decision(
                request, False, "RATE_LIMITED", retry_after, key, bucket
            )
        if reserve:
            bucket["rpm_tokens"] -= need_rpm
            bucket["tpm_tokens"] -= need_tpm
            self._metrics.inc_counter(
                "provider_rate_limit_tokens_reserved_total",
                {
                    "provider": canonical_name(request.provider),
                    "model": canonical_name(request.model),
                    "route_type": request.route_type,
                },
                need_tpm,
            )
        return self._decision(request, True, "ALLOWED", None, key, bucket)

    def _config_for(self, provider: str, model: str) -> ProviderLimitConfig:
        return self._configs.get(
            (canonical_name(provider), canonical_name(model)), self._default
        )

    def _bucket(self, key: str, cfg: ProviderLimitConfig) -> dict[str, float]:
        now = self._now_ms()
        return self._buckets.setdefault(
            key,
            {"rpm_tokens": float(cfg.rpm), "tpm_tokens": float(cfg.tpm), "last_ms": now},
        )

    def _refill(self, bucket: dict[str, float], cfg: ProviderLimitConfig) -> None:
        now = self._now_ms()
        elapsed = max(0, now - int(bucket.get("last_ms", now)))
        if elapsed:
            bucket["rpm_tokens"] = min(
                float(cfg.rpm), bucket["rpm_tokens"] + cfg.rpm * elapsed / 60000.0
            )
            bucket["tpm_tokens"] = min(
                float(cfg.tpm), bucket["tpm_tokens"] + cfg.tpm * elapsed / 60000.0
            )
            bucket["last_ms"] = now

    def _retry_after_backoff_ms(self, provider: str, model: str) -> int:
        until = self._backoff_until.get(provider_backoff_key(provider, model), 0)
        return max(0, until - self._now_ms())

    @staticmethod
    def _wait_ms(available: float, needed: int, per_minute: int) -> int:
        if available >= needed:
            return 0
        missing = needed - available
        return max(1, math.ceil(missing * 60000.0 / max(1, per_minute)))

    def _decision(
        self,
        request: ProviderLimitRequest,
        allowed: bool,
        reason: ProviderLimitReason,
        retry_after_ms: int | None,
        key: str,
        bucket: dict[str, float] | None = None,
    ) -> ProviderLimitDecision:
        labels = {
            "provider": canonical_name(request.provider),
            "model": canonical_name(request.model),
            "route_type": request.route_type,
            "reason": reason,
        }
        self._metrics.inc_counter("provider_rate_limit_decisions_total", labels)
        return ProviderLimitDecision(
            allowed=allowed,
            reason=reason,
            retry_after_ms=retry_after_ms,
            provider_limit_key=key,
            reserved_tokens=request.reserved_tokens,
            remaining_rpm=None if bucket is None else bucket["rpm_tokens"],
            remaining_tpm=None if bucket is None else bucket["tpm_tokens"],
        )


class RedisProviderRateLimiter:
    """Redis Lua-backed provider limiter shared by API and worker replicas."""

    _ACQUIRE_SCRIPT = """
local bucket_key = KEYS[1]
local backoff_key = KEYS[2]
local now = tonumber(ARGV[1])
local rpm = tonumber(ARGV[2])
local tpm = tonumber(ARGV[3])
local need_tpm = tonumber(ARGV[4])
local reserve = tonumber(ARGV[5])
local backoff_until = tonumber(redis.call('GET', backoff_key) or '0')
if backoff_until > now then
  return {0, 'BACKING_OFF', backoff_until - now, 0, 0}
end
local rpm_tokens = tonumber(redis.call('HGET', bucket_key, 'rpm_tokens') or ARGV[2])
local tpm_tokens = tonumber(redis.call('HGET', bucket_key, 'tpm_tokens') or ARGV[3])
local last_ms = tonumber(redis.call('HGET', bucket_key, 'last_refill_ms') or ARGV[1])
local elapsed = math.max(0, now - last_ms)
rpm_tokens = math.min(rpm, rpm_tokens + (rpm * elapsed / 60000))
tpm_tokens = math.min(tpm, tpm_tokens + (tpm * elapsed / 60000))
local rpm_wait = 0
local tpm_wait = 0
if rpm_tokens < 1 then rpm_wait = math.ceil((1 - rpm_tokens) * 60000 / rpm) end
if tpm_tokens < need_tpm then tpm_wait = math.ceil((need_tpm - tpm_tokens) * 60000 / tpm) end
local wait = math.max(rpm_wait, tpm_wait)
if wait > 0 then
  redis.call('HSET', bucket_key, 'rpm_tokens', rpm_tokens, 'tpm_tokens', tpm_tokens, 'last_refill_ms', now, 'updated_at_ms', now)
  redis.call('PEXPIRE', bucket_key, 120000)
  return {0, 'RATE_LIMITED', wait, rpm_tokens, tpm_tokens}
end
if reserve == 1 then
  rpm_tokens = rpm_tokens - 1
  tpm_tokens = tpm_tokens - need_tpm
end
redis.call('HSET', bucket_key, 'rpm_tokens', rpm_tokens, 'tpm_tokens', tpm_tokens, 'last_refill_ms', now, 'updated_at_ms', now)
redis.call('PEXPIRE', bucket_key, 120000)
return {1, 'ALLOWED', 0, rpm_tokens, tpm_tokens}
"""

    _SETTLE_SCRIPT = """
local bucket_key = KEYS[1]
local now = tonumber(ARGV[1])
local tpm = tonumber(ARGV[2])
local debit = tonumber(ARGV[3])
local tpm_tokens = tonumber(redis.call('HGET', bucket_key, 'tpm_tokens') or ARGV[2])
local last_ms = tonumber(redis.call('HGET', bucket_key, 'last_refill_ms') or ARGV[1])
local elapsed = math.max(0, now - last_ms)
tpm_tokens = math.min(tpm, tpm_tokens + (tpm * elapsed / 60000))
tpm_tokens = tpm_tokens - debit
redis.call('HSET', bucket_key, 'tpm_tokens', tpm_tokens, 'last_refill_ms', now, 'updated_at_ms', now)
redis.call('PEXPIRE', bucket_key, 120000)
return {debit, tpm_tokens}
"""

    def __init__(
        self,
        redis_client: Any,
        settings: Settings,
        *,
        metrics: Metrics | None = None,
    ) -> None:
        self._redis = redis_client
        self._settings = settings
        self._metrics = metrics or Metrics()
        self._configs = load_provider_limit_config(settings)
        self._default = ProviderLimitConfig(
            rpm=getattr(settings, "provider_default_rpm", 100000),
            tpm=getattr(settings, "provider_default_tpm", 1000000),
        )

    async def check(self, request: ProviderLimitRequest) -> ProviderLimitDecision:
        return await self._acquire(request, reserve=False)

    async def acquire(self, request: ProviderLimitRequest) -> ProviderLimitDecision:
        return await self._acquire(request, reserve=True)

    async def settle_usage(self, settlement: ProviderUsageSettlement) -> ProviderUsageDecision:
        actual = settlement.actual_total_tokens
        labels = {
            "provider": canonical_name(settlement.provider),
            "model": canonical_name(settlement.model),
            "route_type": settlement.route_type,
        }
        if actual is None:
            self._metrics.inc_counter("provider_usage_missing_total", labels)
            return ProviderUsageDecision(settled=False, usage_missing=True)
        debit = max(0, actual - max(0, settlement.reserved_tokens))
        cfg = self._config_for(settlement.provider, settlement.model)
        result = await self._redis.eval(
            self._SETTLE_SCRIPT,
            1,
            provider_key(settlement.provider, settlement.model),
            int(time.time() * 1000),
            cfg.tpm,
            debit,
        )
        self._metrics.inc_counter(
            "provider_rate_limit_tokens_settled_total", labels, actual
        )
        if debit:
            self._metrics.inc_counter(
                "provider_rate_limit_tokens_debt_total", labels, debit
            )
        return ProviderUsageDecision(
            settled=True,
            debit_tokens=int(result[0]),
            remaining_tpm=float(result[1]),
        )

    async def record_provider_error(
        self,
        provider: str,
        model: str,
        status_code: int,
        retry_after_ms: int | None = None,
    ) -> None:
        if status_code < 429:
            return
        retry_after_ms = retry_after_ms or (30000 if status_code == 429 else 5000)
        await self._redis.psetex(
            provider_backoff_key(provider, model),
            retry_after_ms,
            int(time.time() * 1000) + retry_after_ms,
        )
        self._metrics.inc_counter(
            "provider_errors_total",
            {
                "provider": canonical_name(provider),
                "model": canonical_name(model),
                "status_code": str(status_code),
            },
        )

    async def _acquire(
        self, request: ProviderLimitRequest, *, reserve: bool
    ) -> ProviderLimitDecision:
        cfg = self._config_for(request.provider, request.model)
        started = time.perf_counter()
        try:
            result = await self._redis.eval(
                self._ACQUIRE_SCRIPT,
                2,
                provider_key(request.provider, request.model),
                provider_backoff_key(request.provider, request.model),
                int(time.time() * 1000),
                cfg.rpm,
                cfg.tpm,
                max(1, request.reserved_tokens),
                1 if reserve else 0,
            )
        except Exception:
            if getattr(self._settings, "provider_rate_limit_fail_open", False):
                return ProviderLimitDecision(True, "ALLOWED", reserved_tokens=request.reserved_tokens)
            return ProviderLimitDecision(False, "UNAVAILABLE", retry_after_ms=1000)
        self._metrics.observe_histogram(
            "provider_rate_limit_lua_seconds",
            time.perf_counter() - started,
            {
                "provider": canonical_name(request.provider),
                "model": canonical_name(request.model),
                "route_type": request.route_type,
            },
        )
        allowed = bool(int(result[0]))
        reason = str(result[1])
        retry_after_ms = int(float(result[2] or 0)) or None
        self._metrics.inc_counter(
            "provider_rate_limit_decisions_total",
            {
                "provider": canonical_name(request.provider),
                "model": canonical_name(request.model),
                "route_type": request.route_type,
                "reason": reason,
            },
        )
        if allowed and reserve:
            self._metrics.inc_counter(
                "provider_rate_limit_tokens_reserved_total",
                {
                    "provider": canonical_name(request.provider),
                    "model": canonical_name(request.model),
                    "route_type": request.route_type,
                },
                max(1, request.reserved_tokens),
            )
        return ProviderLimitDecision(
            allowed=allowed,
            reason=reason,  # type: ignore[arg-type]
            retry_after_ms=retry_after_ms,
            provider_limit_key=provider_key(request.provider, request.model),
            reserved_tokens=request.reserved_tokens,
            remaining_rpm=float(result[3]),
            remaining_tpm=float(result[4]),
        )

    def _config_for(self, provider: str, model: str) -> ProviderLimitConfig:
        return self._configs.get(
            (canonical_name(provider), canonical_name(model)), self._default
        )


class DisabledProviderRateLimiter(InMemoryProviderRateLimiter):
    """Fail-open limiter used only when explicitly disabled for local/mock work."""

    async def check(self, request: ProviderLimitRequest) -> ProviderLimitDecision:
        return ProviderLimitDecision(True, "ALLOWED", reserved_tokens=request.reserved_tokens)

    async def acquire(self, request: ProviderLimitRequest) -> ProviderLimitDecision:
        return ProviderLimitDecision(True, "ALLOWED", reserved_tokens=request.reserved_tokens)

    async def settle_usage(self, settlement: ProviderUsageSettlement) -> ProviderUsageDecision:
        return ProviderUsageDecision(settled=True)


def build_provider_limiter(
    settings: Settings,
    *,
    redis_client: Any | None = None,
    metrics: Metrics | None = None,
) -> InMemoryProviderRateLimiter | RedisProviderRateLimiter | DisabledProviderRateLimiter:
    if not getattr(settings, "provider_rate_limit_enabled", True):
        return DisabledProviderRateLimiter(metrics=metrics)
    if redis_client is None:
        return InMemoryProviderRateLimiter(
            default_config=ProviderLimitConfig(
                rpm=getattr(settings, "provider_default_rpm", 100000),
                tpm=getattr(settings, "provider_default_tpm", 1000000),
            ),
            configs=load_provider_limit_config(settings),
            metrics=metrics,
        )
    return RedisProviderRateLimiter(redis_client, settings, metrics=metrics)
