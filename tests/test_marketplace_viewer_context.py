from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.api.identity import ResolvedIdentity
from app.core.schemas import ChatRequest
from app.runtime.marketplace_ai import MarketplaceViewerContext


USER_ID = "marketplace:user:7"
WALLET = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"


def test_chat_api_builds_trusted_viewer_context_from_resolved_headers_only():
    from app.api.routers.chat import _build_marketplace_viewer_context

    request = SimpleNamespace(
        state=SimpleNamespace(
            marketplace_identity=ResolvedIdentity(
                owner_id=WALLET,
                source="marketplace",
                marketplace_user_id=USER_ID,
                marketplace_wallet=WALLET,
            )
        )
    )

    context = _build_marketplace_viewer_context(
        request,
        agent_run_id="run-1",
        conversation_id="conv-1",
        trace_id="trace-1",
    )

    assert context == MarketplaceViewerContext(
        user_id=USER_ID,
        wallet=WALLET,
        agent_run_id="run-1",
        conversation_id="conv-1",
        trace_id="trace-1",
    )


def test_batch_payload_keeps_viewer_separate_from_model_run_context():
    from app.api.routers.chat import _build_payload

    viewer = MarketplaceViewerContext(
        user_id=USER_ID,
        wallet=WALLET,
        agent_run_id="run-1",
        conversation_id="conv-1",
        trace_id="trace-1",
    )
    body = ChatRequest(
        message="hello",
        proxy_payload={"agent": {"address": "0x1111111111111111111111111111111111111111"}},
    )

    payload = _build_payload(
        "run-1",
        "conv-1",
        "trace-1",
        body,
        marketplace_viewer_context=viewer,
    )

    assert payload["marketplace_viewer_context"] == viewer.to_payload()
    assert "marketplace_viewer_context" not in payload["run_context"]


def test_enqueue_run_forwards_viewer_context_to_celery(monkeypatch):
    from app.api import runner_gateway

    captured = {}

    class _Task:
        @staticmethod
        def delay(**kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(runner_gateway, "_load_run_task", lambda: _Task())
    viewer_payload = {
        "user_id": USER_ID,
        "wallet": WALLET,
        "agent_run_id": "run-1",
        "conversation_id": "conv-1",
        "trace_id": "trace-1",
    }

    runner_gateway.enqueue_run(
        {
            "agent_run_id": "run-1",
            "conversation_id": "conv-1",
            "trace_id": "trace-1",
            "message": "hello",
            "task_id": "task-1",
            "marketplace_viewer_context": viewer_payload,
        }
    )

    assert captured["marketplace_viewer_context"] == viewer_payload
    assert captured["task_id"] == "task-1"


async def test_realtime_runner_forwards_typed_viewer_context_to_orchestrator():
    from app.runtime.runner import RealtimeRunRequest, RealtimeRunner
    from tests.harness_fakes import FakeRunLease

    captured = {}

    class _Orchestrator:
        async def run(self, **kwargs):
            captured.update(kwargs)
            return "ok"

    viewer = MarketplaceViewerContext(
        user_id=USER_ID,
        wallet=WALLET,
        agent_run_id="run-1",
        conversation_id="conv-1",
        trace_id="trace-1",
    )
    runner = RealtimeRunner(
        orchestrator_factory=lambda: _Orchestrator(),
        run_lease=FakeRunLease(),
        heartbeat_interval_s=0,
    )

    await runner.run_chat(
        RealtimeRunRequest(
            agent_run_id="run-1",
            conversation_id="conv-1",
            user_id=WALLET,
            trace_id="trace-1",
            message="hello",
            metadata={},
            accepted_at=0,
            marketplace_viewer_context=viewer,
        )
    )

    assert captured["marketplace_viewer_context"] is viewer


class TestBatchWorkerLoop:
    """Batch worker tests run on the stdlib loop, matching the Celery worker process."""

    @pytest.fixture
    def event_loop_policy(self):
        return asyncio.DefaultEventLoopPolicy()

    async def test_batch_worker_forwards_viewer_payload_to_orchestration(
        self, monkeypatch
    ):
        from app.tasks import agent_tasks

        captured = {}
        viewer_payload = {
            "user_id": USER_ID,
            "wallet": WALLET,
            "agent_run_id": "run-1",
            "conversation_id": "conv-1",
            "trace_id": "trace-1",
        }

        async def orchestrate(**kwargs):
            captured.update(kwargs)
            return {"content": "ok", "intent": None}

        async def noop(*_args, **_kwargs):
            return None

        monkeypatch.setattr(agent_tasks, "_resolve_orchestrator", lambda: orchestrate)
        monkeypatch.setattr(agent_tasks.run_store, "ensure_run", noop)
        monkeypatch.setattr(agent_tasks.run_store, "mark_run_running", noop)
        monkeypatch.setattr(agent_tasks.run_store, "mark_run_succeeded", noop)

        await agent_tasks._execute(
            "run-1",
            "conv-1",
            "trace-1",
            "hello",
            marketplace_viewer_context=viewer_payload,
        )

        assert captured["marketplace_viewer_context"] == viewer_payload

    async def test_batch_worker_does_not_overwrite_failed_orchestration_status(
        self, monkeypatch
    ):
        from app.tasks import agent_tasks

        calls: list[tuple[str, tuple]] = []

        async def orchestrate(**_kwargs):
            return {
                "content": "safe fallback",
                "intent": None,
                "status": "FAILED",
                "error": "ORCHESTRATION_FAILED",
            }

        async def record(name, *args, **_kwargs):
            calls.append((name, args))

        monkeypatch.setattr(agent_tasks, "_resolve_orchestrator", lambda: orchestrate)
        monkeypatch.setattr(
            agent_tasks.run_store,
            "ensure_run",
            lambda *args, **kwargs: record("ensure", *args, **kwargs),
        )
        monkeypatch.setattr(
            agent_tasks.run_store,
            "mark_run_running",
            lambda *args, **kwargs: record("running", *args, **kwargs),
        )
        monkeypatch.setattr(
            agent_tasks.run_store,
            "mark_run_succeeded",
            lambda *args, **kwargs: record("succeeded", *args, **kwargs),
        )
        monkeypatch.setattr(
            agent_tasks.run_store,
            "mark_run_failed",
            lambda *args, **kwargs: record("failed", *args, **kwargs),
        )

        result = await agent_tasks._execute("run-failed", "conv", "trace", "hello")

        assert result["status"] == "FAILED"
        assert any(name == "failed" for name, _args in calls)
        assert all(name != "succeeded" for name, _args in calls)

    async def test_batch_orchestration_rehydrates_only_execution_bound_context(
        self, monkeypatch
    ):
        from app.runtime import deps as deps_module
        from app.runtime import orchestrator as orchestrator_module

        captured = []

        class _Orchestrator:
            def __init__(self, _deps):
                pass

            async def run(self, **kwargs):
                captured.append(kwargs["marketplace_viewer_context"])
                return "ok"

        monkeypatch.setattr(deps_module, "build_deps", lambda: object())
        monkeypatch.setattr(orchestrator_module, "AgentOrchestrator", _Orchestrator)
        valid_payload = {
            "user_id": USER_ID,
            "wallet": WALLET,
            "agent_run_id": "run-1",
            "conversation_id": "conv-1",
            "trace_id": "trace-1",
        }

        await orchestrator_module.run_orchestration(
            agent_run_id="run-1",
            conversation_id="conv-1",
            trace_id="trace-1",
            user_message="hello",
            marketplace_viewer_context=valid_payload,
        )
        await orchestrator_module.run_orchestration(
            agent_run_id="run-1",
            conversation_id="conv-1",
            trace_id="trace-1",
            user_message="hello",
            marketplace_viewer_context={**valid_payload, "agent_run_id": "run-other"},
        )

        assert isinstance(captured[0], MarketplaceViewerContext)
        assert captured[1] is None


def test_viewer_context_values_never_appear_in_masked_plan_context():
    from app.core.config import Settings
    from app.runtime.orchestrator import AgentOrchestrator

    plan = AgentOrchestrator._plan_snapshot(
        "realtime",
        {},
        Settings(_env_file=None),
        run_context={
            "marketplace_identity": {
                "user_id": USER_ID,
                "wallet_address": WALLET,
            },
            "wallet_address": WALLET,
        },
    )

    rendered = repr(plan)
    assert USER_ID not in rendered
    assert WALLET not in rendered
    assert "[masked:identity]" in rendered


def test_viewer_context_repr_masks_identity_values():
    viewer = MarketplaceViewerContext(
        user_id=USER_ID,
        wallet=WALLET,
        agent_run_id="run-1",
        conversation_id="conv-1",
    )

    rendered = repr(viewer)
    assert USER_ID not in rendered
    assert WALLET not in rendered
    assert rendered.count("[masked:identity]") == 2
