from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
import pytest


async def test_lifespan_wires_shared_redis_runtime_resources(monkeypatch):
    from app.api import lifespan as lifespan_module

    class _FakeRedis:
        def __init__(self) -> None:
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True

    redis = _FakeRedis()
    monkeypatch.setattr(
        lifespan_module.Redis,
        "from_url",
        lambda *args, **kwargs: redis,
    )
    monkeypatch.setattr(
        lifespan_module,
        "get_settings",
        lambda: SimpleNamespace(
            redis_url="redis://test/0",
            rate_limit_per_min=1000,
            log_level="WARNING",
            realtime_runner_max_concurrency=123,
            run_max_runtime_s=456,
            llm_provider="mock",
            provider_rate_limit_enabled=True,
            provider_key_pool_file="",
            provider_key_pool_scope="account",
            provider_key_pool_strategy="least_wait_round_robin",
            zai_api_keys_file="",
        ),
    )
    monkeypatch.setattr(lifespan_module, "configure_logging", lambda *args, **kwargs: None)

    app = FastAPI()

    async with lifespan_module.lifespan(app):
        assert app.state.redis is redis
        assert app.state.metrics is not None
        assert app.state.event_bus._client is redis
        assert app.state.conversation_lock._client is redis
        assert app.state.provider_key_pool.status == "mock"
        assert app.state.realtime_runner._run_lease._client is redis
        assert app.state.realtime_runner._event_bus is app.state.event_bus
        assert app.state.realtime_runner._max_concurrency == 123
        assert app.state.realtime_runner._max_runtime_s == 456
        orchestrator = app.state.realtime_runner._orchestrator_factory()
        assert orchestrator._deps.event_bus is app.state.event_bus
        assert orchestrator._deps.metrics is app.state.metrics

    assert redis.closed is True


def test_event_bus_wiring_fails_closed_when_stream_bus_is_unavailable(monkeypatch):
    from app.api import lifespan as lifespan_module
    import app.bus

    monkeypatch.setattr(
        app.bus,
        "create_event_bus",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("stream bus unavailable")
        ),
    )

    with pytest.raises(RuntimeError, match="stream bus unavailable"):
        lifespan_module._build_event_bus("redis://test/0")
