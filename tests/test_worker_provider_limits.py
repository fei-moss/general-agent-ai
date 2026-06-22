from __future__ import annotations

from types import SimpleNamespace

import pytest
from celery.exceptions import Retry

from app.runtime.provider_limits import ProviderRateLimitError


def test_celery_worker_retries_after_provider_limit(monkeypatch):
    from app.tasks import agent_tasks

    async def _raise_limit(*args, **kwargs):
        raise ProviderRateLimitError("RATE_LIMITED", retry_after_ms=2500)

    def _retry(*, exc, countdown):
        assert isinstance(exc, ProviderRateLimitError)
        assert countdown == 2
        raise Retry()

    monkeypatch.setattr(agent_tasks, "_execute", _raise_limit)
    monkeypatch.setattr(agent_tasks.run_agent_task, "retry", _retry)

    with pytest.raises(Retry):
        agent_tasks.run_agent_task.run("run-1", "conv-1", "trace-1", "hello")


def test_celery_worker_process_init_disposes_inherited_db_pool(monkeypatch):
    from app.db import session as db_session
    from app.tasks.celery_app import _dispose_inherited_db_pool

    calls: list[bool] = []

    def _dispose(*, close: bool) -> None:
        calls.append(close)

    monkeypatch.setattr(
        db_session,
        "engine",
        SimpleNamespace(sync_engine=SimpleNamespace(dispose=_dispose)),
    )

    _dispose_inherited_db_pool()

    assert calls == [False]


def test_run_coro_disposes_stale_db_pool_before_new_loop(monkeypatch):
    from app.db import session as db_session
    from app.tasks.async_bridge import run_coro

    calls: list[bool] = []

    def _dispose(*, close: bool) -> None:
        calls.append(close)

    async def _value() -> str:
        return "ok"

    monkeypatch.setattr(
        db_session,
        "engine",
        SimpleNamespace(sync_engine=SimpleNamespace(dispose=_dispose)),
    )

    assert run_coro(_value()) == "ok"
    assert calls == [False]
