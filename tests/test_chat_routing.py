from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from app.core.enums import RunStatus
from app.core.models import Conversation, Message
from app.core.schemas import ChatRequest


def test_chat_routing_harness_can_represent_route_metadata():
    metadata = {"mode": "auto", "task_type": "chat"}

    assert metadata["mode"] in {"auto", "realtime", "batch"}
    assert metadata["task_type"] == "chat"


def test_auto_route_selects_realtime_for_normal_chat():
    from app.api.routers.chat import select_route_type

    assert select_route_type({"task_type": "chat"}, runtime_mode="auto") == "realtime"


def test_auto_route_selects_batch_for_file_or_slow_tasks():
    from app.api.routers.chat import select_route_type

    assert select_route_type({"task_type": "file_analysis"}, runtime_mode="auto") == "batch"
    assert select_route_type({"task_type": "slow_tool"}, runtime_mode="auto") == "batch"


def test_runtime_mode_celery_forces_batch_route():
    from app.api.routers.chat import select_route_type

    assert select_route_type({"mode": "realtime"}, runtime_mode="celery") == "batch"


def test_accepted_response_preserves_existing_fields_and_adds_route_type():
    from app.api.routers.chat import _accepted

    accepted = _accepted("conv-1", "run-1", "trace-1", route_type="realtime")

    assert accepted.conversation_id == "conv-1"
    assert accepted.agent_run_id == "run-1"
    assert accepted.route_type == "realtime"


def test_accepted_response_includes_encoded_user_uuid_on_existing_stream_urls():
    from app.api.routers.chat import _accepted

    accepted = _accepted(
        "conv-1",
        "run-1",
        "trace-1",
        route_type="realtime",
        user_uuid="market user/1",
    )

    assert accepted.stream_url == "/stream/run-1?user_uuid=market+user%2F1"
    assert accepted.ws_url == "/ws/run-1?user_uuid=market+user%2F1"


def test_chat_request_accepts_proxy_payload_as_upstream_context():
    body = ChatRequest(
        message="hello",
        proxy_payload={
            "marketplace_agent": {
                "address": "0x17B09FC949f031dbD540D4caDE59805A08Ee5043"
            }
        },
    )

    assert body.run_context == body.proxy_payload
    assert body.run_context["marketplace_agent"]["address"].startswith("0x17")


def test_chat_request_exposes_normalized_marketplace_identity_accessor():
    body = ChatRequest(
        message="hello",
        proxy_payload={
            "marketplace_identity": {
                "user_id": "marketplace:user:7",
                "wallet_address": "0xAbCdEfAbCdEfAbCdEfAbCdEfAbCdEfAbCdEfAbCd",
            }
        },
    )

    assert body.marketplace_identity is not None
    assert body.marketplace_identity.user_id == "marketplace:user:7"
    assert (
        body.marketplace_identity.wallet_address
        == "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
    )


def test_chat_request_projects_metadata_agent_context_to_run_context():
    body = ChatRequest(
        message="hello",
        metadata={
            "agent_context": {
                "agent_address": "0x5d277412d92f7c77eFd938325Dc43aA9c32bF036",
                "agent_id": "#1053",
                "contract_address": "0x5d277412d92f7c77eFd938325Dc43aA9c32bF036",
                "description": "1111",
                "protocol": "Agent",
            },
            "current_agent_address": "0x5d277412d92f7c77eFd938325Dc43aA9c32bF036",
            "page_context": "agent_detail",
            "mode": "realtime",
            "task_type": "chat",
        },
    )

    assert body.proxy_payload == {}
    assert body.run_context["agent_address"] == "0x5d277412d92f7c77eFd938325Dc43aA9c32bF036"
    assert body.run_context["agent"]["address"] == "0x5d277412d92f7c77eFd938325Dc43aA9c32bF036"
    assert body.run_context["agent"]["agent_id"] == "#1053"
    assert body.run_context["agent"]["protocol"] == "Agent"


def test_chat_request_prefers_current_agent_address_over_agent_context_address():
    body = ChatRequest(
        message="hello",
        metadata={
            "agent_context": {
                "agent_address": "0x1111111111111111111111111111111111111111",
                "contract_address": "0x2222222222222222222222222222222222222222",
            },
            "current_agent_address": "0x3333333333333333333333333333333333333333",
        },
        proxy_payload={"user_address": "0x4444444444444444444444444444444444444444"},
    )

    assert body.run_context["agent_address"] == "0x3333333333333333333333333333333333333333"
    assert body.run_context["agent"]["address"] == "0x3333333333333333333333333333333333333333"
    assert body.run_context["agent"]["agent_address"] == "0x1111111111111111111111111111111111111111"
    assert body.run_context["user_address"] == "0x4444444444444444444444444444444444444444"


def test_chat_request_preserves_existing_proxy_agent_fields_when_metadata_sets_address():
    body = ChatRequest(
        message="hello",
        metadata={
            "current_agent_address": "0x3333333333333333333333333333333333333333",
        },
        proxy_payload={
            "agent": {
                "address": "0x1111111111111111111111111111111111111111",
                "display_name": "Legacy Agent",
            }
        },
    )

    assert body.run_context["agent_address"] == "0x3333333333333333333333333333333333333333"
    assert body.run_context["agent"]["address"] == "0x3333333333333333333333333333333333333333"
    assert body.run_context["agent"]["display_name"] == "Legacy Agent"


def test_chat_request_rejects_run_context_request_field():
    with pytest.raises(ValidationError):
        ChatRequest(
            message="hello",
            run_context={
                "marketplace_agent": {
                    "address": "0x1111111111111111111111111111111111111111"
                }
            },
        )


def test_chat_request_exposes_empty_proxy_payload_as_empty_run_context():
    body = ChatRequest(message="hello")

    assert body.proxy_payload == {}
    assert body.run_context == {}


def test_chat_request_ignores_unrelated_extra_fields_by_existing_default():
    context = {"tenant": "alpha"}

    body = ChatRequest(
        message="hello",
        proxy_payload={"tenant": "alpha"},
        ignored="value",
    )

    assert body.run_context == context
    assert body.proxy_payload == context


async def test_chat_returned_conversation_id_can_fetch_detail(monkeypatch):
    from app.api import deps
    from app.api.main import create_app
    from app.api.repos import Repos
    from app.core.config import get_settings

    monkeypatch.setenv("LLM_PROVIDER", "mock")
    get_settings.cache_clear()

    class _MemorySession:
        def __init__(self) -> None:
            self.rows = {}

        async def get(self, model, key):
            return self.rows.get((model, key))

        def add(self, entity) -> None:
            self.rows[(type(entity), entity.id)] = entity

        async def flush(self) -> None:
            return None

        async def refresh(self, entity) -> None:
            now = datetime.now(UTC)
            if isinstance(entity, Conversation):
                entity.created_at = entity.created_at or now
                entity.updated_at = entity.updated_at or now
            if isinstance(entity, Message):
                entity.created_at = entity.created_at or now
                entity.meta = entity.meta or {}

        async def commit(self) -> None:
            return None

    class _MemoryRepos(Repos):
        async def get_conversation_with_messages(self, conversation_id):
            conversation = await self.get_conversation(conversation_id)
            if conversation is None:
                return None
            conversation.messages = [
                entity
                for (model, _), entity in self.session.rows.items()
                if model is Message and entity.conversation_id == conversation_id
            ]
            return conversation

    class _Lease:
        async def renew(self):
            return True

        async def release(self):
            return True

    class _Lock:
        async def acquire(self, *args, **kwargs):
            return _Lease()

    class _CapacitySlot:
        async def release(self):
            return None

    class _Runner:
        def try_acquire_capacity(self):
            return _CapacitySlot()

        async def run_chat(self, request, *, conversation_lease=None, capacity_slot=None):
            if conversation_lease is not None:
                await conversation_lease.release()
            if capacity_slot is not None:
                await capacity_slot.release()

    app = create_app()
    app.state.conversation_lock = _Lock()
    app.state.realtime_runner = _Runner()
    repos = _MemoryRepos(_MemorySession())

    async def override_repos():
        yield repos

    app.dependency_overrides[deps.get_repos] = override_repos
    headers = {"Authorization": "Bearer user-conversation-detail"}

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/chat",
                headers=headers,
                json={"message": "hello"},
            )
            assert resp.status_code == 202
            conversation_id = resp.json()["conversation_id"]

            detail = await client.get(
                f"/conversations/{conversation_id}",
                headers=headers,
            )
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    assert detail.status_code == 200
    assert detail.json()["id"] == conversation_id
    assert detail.json()["messages"][0]["content"] == "hello"


async def test_chat_accepts_url_user_uuid_and_prefers_it_over_headers(monkeypatch):
    from app.api import deps
    from app.api.main import create_app
    from app.api.repos import Repos
    from app.core.config import get_settings

    monkeypatch.setenv("LLM_PROVIDER", "mock")
    get_settings.cache_clear()

    class _MemorySession:
        def __init__(self) -> None:
            self.rows = {}

        async def get(self, model, key):
            return self.rows.get((model, key))

        def add(self, entity) -> None:
            self.rows[(type(entity), entity.id)] = entity

        async def flush(self) -> None:
            return None

        async def refresh(self, entity) -> None:
            now = datetime.now(UTC)
            if isinstance(entity, Conversation):
                entity.created_at = entity.created_at or now
                entity.updated_at = entity.updated_at or now
            if isinstance(entity, Message):
                entity.created_at = entity.created_at or now
                entity.meta = entity.meta or {}

        async def commit(self) -> None:
            return None

    class _Lease:
        async def renew(self):
            return True

        async def release(self):
            return True

    class _Lock:
        async def acquire(self, *args, **kwargs):
            return _Lease()

    class _CapacitySlot:
        async def release(self):
            return None

    class _Runner:
        def try_acquire_capacity(self):
            return _CapacitySlot()

        async def run_chat(self, request, *, conversation_lease=None, capacity_slot=None):
            if conversation_lease is not None:
                await conversation_lease.release()
            if capacity_slot is not None:
                await capacity_slot.release()

    app = create_app()
    app.state.conversation_lock = _Lock()
    app.state.realtime_runner = _Runner()
    repos = Repos(_MemorySession())

    async def override_repos():
        yield repos

    app.dependency_overrides[deps.get_repos] = override_repos

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/chat?user_uuid=market-user-1",
                headers={"Authorization": f"Bearer {'u' * 128}"},
                json={"message": "hello", "stream": True},
            )
            body = resp.json()
            status_resp = await client.get(
                f"/runs/{body['agent_run_id']}?user_uuid=market-user-1"
            )
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    assert resp.status_code == 202
    assert body["stream_url"].startswith("/stream/run_")
    assert body["stream_url"].endswith("?user_uuid=market-user-1")
    assert body["ws_url"].startswith("/ws/run_")
    assert body["ws_url"].endswith("?user_uuid=market-user-1")
    assert status_resp.status_code == 200
    assert status_resp.json()["agent_run_id"] == body["agent_run_id"]
    assert status_resp.json()["status"] == "PENDING"


async def test_removed_api_v1_chat_route_is_not_registered():
    from app.api import deps
    from app.api.main import create_app

    app = create_app()

    async def repos_must_not_be_touched():
        raise AssertionError("removed /api/v1/chat route must stop before repositories")
        yield

    app.dependency_overrides[deps.get_repos] = repos_must_not_be_touched

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/api/v1/chat?user_uuid=market-user-1",
                json={"message": "hello"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


async def test_chat_rejects_overlong_url_user_uuid_before_side_effects():
    from app.api import deps
    from app.api.main import create_app

    app = create_app()

    async def repos_must_not_be_touched():
        raise AssertionError("overlong user_uuid must stop before repositories")
        yield

    app.dependency_overrides[deps.get_repos] = repos_must_not_be_touched

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                f"/chat?user_uuid={'u' * 65}",
                json={"message": "hello"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 422
    assert resp.json()["detail"] == "USER_UUID_TOO_LONG"


async def test_legacy_chat_rejects_overlong_header_user_before_side_effects():
    from app.api import deps
    from app.api.main import create_app

    app = create_app()

    async def repos_must_not_be_touched():
        raise AssertionError("overlong header user must stop before repositories")
        yield

    app.dependency_overrides[deps.get_repos] = repos_must_not_be_touched

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/chat",
                headers={"Authorization": f"Bearer {'u' * 65}"},
                json={"message": "hello"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 422
    assert resp.json()["detail"] == "USER_ID_TOO_LONG"


async def test_duplicate_idempotency_claim_replays_before_conversation_lock():
    from app.api.routers import chat
    from app.api.idempotency import chat_request_hash

    request_hash = chat_request_hash(
        message="hello",
        conversation_id="conv-1",
        metadata={"mode": "realtime"},
        run_context={"tenant": "alpha"},
    )

    class _ExistingRecord:
        def __init__(self) -> None:
            self.request_hash = request_hash
            self.agent_run_id = "run-existing"
            self.response = {
                "conversation_id": "conv-1",
                "agent_run_id": "run-existing",
                "trace_id": "trace-existing",
                "status": "PENDING",
                "stream_url": "/stream/run-existing",
                "ws_url": "/ws/run-existing",
                "route_type": "realtime",
            }

    class _Repos:
        async def get_idempotency_record(self, user_id, idempotency_key):
            return None

        async def claim_idempotency_record(self, **kwargs):
            return _ExistingRecord(), False

        async def get_run(self, run_id):
            return SimpleNamespace(status=RunStatus.RUNNING)

    class _Lock:
        async def acquire(self, *args, **kwargs):
            raise AssertionError("lock must not be acquired for idempotency replay")

    monkey_state = SimpleNamespace(conversation_lock=_Lock())
    request = SimpleNamespace(
        headers={"idempotency-key": "key-1"},
        state=SimpleNamespace(trace_id="trace-new"),
        app=SimpleNamespace(state=monkey_state),
    )

    response = await chat.create_chat(
            ChatRequest(
                message="hello",
                conversation_id="conv-1",
                metadata={"mode": "realtime"},
                proxy_payload={"tenant": "alpha"},
            ),
        request,
        "user-1",
        _Repos(),
    )

    assert response.agent_run_id == "run-existing"
    assert response.status is RunStatus.RUNNING


async def test_stream_false_is_rejected_before_side_effects():
    from app.api.routers import chat

    class _Repos:
        async def get_idempotency_record(self, *args, **kwargs):
            raise AssertionError("repositories must not be touched")

    class _Lock:
        async def acquire(self, *args, **kwargs):
            raise AssertionError("lock must not be acquired")

    request = SimpleNamespace(
        headers={"idempotency-key": "key-sync"},
        state=SimpleNamespace(trace_id="trace-sync"),
        app=SimpleNamespace(state=SimpleNamespace(conversation_lock=_Lock())),
    )

    with pytest.raises(Exception) as exc:
        await chat.create_chat(
            ChatRequest(
                message="hello",
                stream=False,
                metadata={"mode": "realtime"},
            ),
            request,
            "user-1",
            _Repos(),
        )

    assert getattr(exc.value, "status_code", None) == 422
    assert getattr(exc.value, "detail", None) == "STREAM_FALSE_NOT_SUPPORTED"


async def test_forbidden_conversation_does_not_reserve_realtime_capacity():
    from app.api.routers import chat

    class _Repos:
        async def get_idempotency_record(self, user_id, idempotency_key):
            return None

        async def get_conversation(self, conversation_id):
            return SimpleNamespace(id=conversation_id, user_id="other-user")

    class _Runner:
        def __init__(self) -> None:
            self.reserve_calls = 0

        def try_acquire_capacity(self):
            self.reserve_calls += 1
            raise AssertionError("capacity must not be reserved before owner check")

    runner = _Runner()
    request = SimpleNamespace(
        headers={},
        state=SimpleNamespace(trace_id="trace-1"),
        app=SimpleNamespace(state=SimpleNamespace(realtime_runner=runner)),
    )

    with pytest.raises(Exception) as exc:
        await chat.create_chat(
            ChatRequest(
                message="hello",
                conversation_id="conv-other",
                metadata={"mode": "realtime"},
            ),
            request,
            "user-1",
            _Repos(),
        )

    assert getattr(exc.value, "status_code", None) == 403
    assert runner.reserve_calls == 0


async def test_dispatch_realtime_keeps_strong_reference_until_task_done():
    from app.api.routers import chat

    started = asyncio.Event()
    finish = asyncio.Event()

    class _Runner:
        async def run_chat(self, request, *, conversation_lease=None, capacity_slot=None):
            started.set()
            await finish.wait()

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(realtime_runner=_Runner())))
    payload = {
        "agent_run_id": "run-bg-1",
        "conversation_id": "conv-1",
        "trace_id": "trace-1",
        "message": "hello",
        "metadata": {},
    }

    task = chat._dispatch_realtime(request, payload, "user-1", None)
    await asyncio.wait_for(started.wait(), timeout=1)

    assert task in chat._BACKGROUND_TASKS
    finish.set()
    await asyncio.wait_for(task, timeout=1)
    assert task not in chat._BACKGROUND_TASKS


def test_build_payload_includes_generic_run_context():
    from app.api.routers.chat import _build_payload

    payload = _build_payload(
        "run-1",
        "conv-1",
        "trace-1",
        ChatRequest(
            message="hello",
            metadata={"mode": "batch"},
            proxy_payload={"fixture": {"id": "ctx-1"}},
        ),
    )

    assert payload["run_context"] == {"fixture": {"id": "ctx-1"}}


def test_build_payload_includes_proxy_payload_as_run_context():
    from app.api.routers.chat import _build_payload

    payload = _build_payload(
        "run-1",
        "conv-1",
        "trace-1",
        ChatRequest(
            message="hello",
            metadata={"mode": "batch"},
            proxy_payload={"fixture": {"id": "ctx-proxy"}},
        ),
    )

    assert payload["run_context"] == {"fixture": {"id": "ctx-proxy"}}


async def test_dispatch_realtime_forwards_run_context_to_runner():
    from app.api.routers import chat

    seen = {}

    class _Runner:
        async def run_chat(self, request, *, conversation_lease=None, capacity_slot=None):
            seen["run_context"] = request.run_context

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(realtime_runner=_Runner())))
    payload = {
        "agent_run_id": "run-bg-context",
        "conversation_id": "conv-1",
        "trace_id": "trace-1",
        "message": "hello",
        "metadata": {},
        "run_context": {"fixture": {"id": "ctx-1"}},
    }

    task = chat._dispatch_realtime(request, payload, "user-1", None)
    await asyncio.wait_for(task, timeout=1)

    assert seen["run_context"] == {"fixture": {"id": "ctx-1"}}


async def test_provider_preflight_estimates_message_metadata_and_run_context():
    from app.api.routers.chat import _apply_provider_preflight

    captured = {}

    class _Limiter:
        async def check(self, request):
            captured["estimated_input_tokens"] = request.estimated_input_tokens
            return SimpleNamespace(allowed=True)

    body = ChatRequest(
        message="hi",
        metadata={"mode": "realtime"},
        proxy_payload={"long_context": "x" * 300},
    )
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(provider_limiter=_Limiter())))
    settings = SimpleNamespace(
        llm_provider="zai",
        zai_model="glm-5.2",
        provider_default_max_output_tokens=1024,
        provider_realtime_preflight_timeout_ms=100,
        provider_realtime_degrade_to_batch=True,
    )

    route_type = await _apply_provider_preflight(
        body,
        request,
        "realtime",
        settings=settings,
        user_id="user-1",
    )

    assert route_type == "realtime"
    assert captured["estimated_input_tokens"] > 50


def test_missing_realtime_runner_fails_closed_instead_of_creating_fallback():
    from app.api.routers import chat

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    with pytest.raises(Exception) as exc:
        chat._get_realtime_runner(request)

    assert getattr(exc.value, "status_code", None) == 503


async def test_realtime_explicit_provider_limit_returns_429_without_run():
    from app.api.routers import chat
    from app.core.config import Settings

    class _Limiter:
        async def check(self, request):
            return SimpleNamespace(
                allowed=False,
                reason="RATE_LIMITED",
                retry_after_ms=2500,
            )

    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(provider_limiter=_Limiter()))
    )

    with pytest.raises(Exception) as exc:
        await chat._apply_provider_preflight(
            ChatRequest(message="hello", metadata={"mode": "realtime"}),
            request,
            "realtime",
            settings=Settings(
                _env_file=None,
                llm_provider="openai",
                openai_api_key="sk-test",
            ),
            user_id="user-1",
        )

    assert getattr(exc.value, "status_code", None) == 429
    assert getattr(exc.value, "headers", {}).get("Retry-After") == "3"


async def test_auto_mode_provider_limit_degrades_to_batch():
    from app.api.routers import chat
    from app.core.config import Settings

    class _Limiter:
        async def check(self, request):
            return SimpleNamespace(
                allowed=False,
                reason="RATE_LIMITED",
                retry_after_ms=1000,
            )

    body = ChatRequest(message="hello", metadata={"mode": "auto"})
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(provider_limiter=_Limiter()))
    )

    route = await chat._apply_provider_preflight(
        body,
        request,
        "realtime",
        settings=Settings(
            _env_file=None,
            llm_provider="openai",
            openai_api_key="sk-test",
        ),
        user_id="user-1",
    )

    assert route == "batch"
    assert body.metadata["degraded"] is True
    assert body.metadata["degraded_reason"] == "provider_rate_limited"
