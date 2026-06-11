from __future__ import annotations

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
