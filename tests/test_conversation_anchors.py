from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import UniqueConstraint

from app.api.repos import Repos
from app.core.models import ConversationAnchor
from app.core.schemas import ChatRequest, ConversationAnchorIn


def test_chat_request_accepts_normalized_conversation_anchor():
    body = ChatRequest(
        message="hello",
        conversation_anchor={"type": " Match ", "key": " USA vs ENG "},
    )

    assert body.conversation_anchor == ConversationAnchorIn(
        type="match",
        key="usa-vs-eng",
    )


def test_conversation_anchor_model_has_unique_user_type_key_contract():
    columns = ConversationAnchor.__table__.columns

    assert {
        "id",
        "conversation_id",
        "user_id",
        "anchor_type",
        "anchor_key",
    }.issubset(set(columns.keys()))
    unique_columns = {
        tuple(constraint.columns.keys())
        for constraint in ConversationAnchor.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("user_id", "anchor_type", "anchor_key") in unique_columns


async def test_repos_can_find_and_bind_conversation_anchor():
    class _Result:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    class _Session:
        def __init__(self) -> None:
            self.rows = {}
            self.added = []
            self.anchor = None

        async def get(self, model, key):
            return self.rows.get((model, key))

        def add(self, entity) -> None:
            self.added.append(entity)
            self.rows[(type(entity), entity.id)] = entity
            if isinstance(entity, ConversationAnchor):
                self.anchor = entity

        async def flush(self) -> None:
            return None

        async def refresh(self, entity) -> None:
            return None

        async def execute(self, statement):
            return _Result(self.anchor)

    session = _Session()
    repos = Repos(session)
    conversation = await repos.ensure_conversation("conv-anchor", "user-1")
    bound = await repos.bind_conversation_anchor(
        conversation_id=conversation.id,
        user_id="user-1",
        anchor_type="match",
        anchor_key="usa-vs-eng",
    )
    found = await repos.find_conversation_by_anchor(
        user_id="user-1",
        anchor_type="match",
        anchor_key="usa-vs-eng",
    )

    assert bound.conversation_id == "conv-anchor"
    assert found is conversation


async def test_chat_reuses_existing_anchor_when_conversation_id_absent(monkeypatch):
    from app.api.routers import chat

    class _Repos:
        def __init__(self) -> None:
            self.created_runs = []
            self.committed = False

        async def get_idempotency_record(self, *args, **kwargs):
            return None

        async def find_conversation_by_anchor(self, **kwargs):
            assert kwargs == {
                "user_id": "user-1",
                "anchor_type": "match",
                "anchor_key": "usa-vs-eng",
            }
            return SimpleNamespace(id="conv-existing", user_id="user-1")

        async def get_conversation(self, conversation_id):
            return SimpleNamespace(id=conversation_id, user_id="user-1")

        async def ensure_conversation(self, conversation_id, user_id):
            assert conversation_id == "conv-existing"
            return SimpleNamespace(id="conv-existing", user_id=user_id)

        async def bind_conversation_anchor(self, **kwargs):
            assert kwargs == {
                "conversation_id": "conv-existing",
                "user_id": "user-1",
                "anchor_type": "match",
                "anchor_key": "usa-vs-eng",
            }
            return None

        async def add_message(self, **kwargs):
            return SimpleNamespace(id="msg-1")

        async def create_run(self, *args, **kwargs):
            self.created_runs.append((args, kwargs))

        async def create_queued_task(self, **kwargs):
            return None

        async def commit(self):
            self.committed = True

    class _Lease:
        async def release(self):
            return None

    class _Lock:
        def __init__(self) -> None:
            self.keys = []

        async def acquire(self, key, owner, ttl_s):
            self.keys.append(key)
            return _Lease()

    class _Slot:
        async def release(self):
            return None

    class _Runner:
        def try_acquire_capacity(self):
            return _Slot()

        async def run_chat(self, request, *, conversation_lease=None, capacity_slot=None):
            if conversation_lease is not None:
                await conversation_lease.release()
            if capacity_slot is not None:
                await capacity_slot.release()

    repos = _Repos()
    lock = _Lock()
    request = SimpleNamespace(
        headers={},
        state=SimpleNamespace(trace_id="trace-1"),
        app=SimpleNamespace(
            state=SimpleNamespace(
                conversation_lock=lock,
                realtime_runner=_Runner(),
            )
        ),
    )
    monkeypatch.setattr(
        chat,
        "get_settings",
        lambda: SimpleNamespace(chat_runtime_mode="realtime", llm_provider="mock"),
    )

    accepted = await chat.create_chat(
        ChatRequest(
            message="hello",
            metadata={"mode": "realtime"},
            run_context={
                "public": {"id": "ctx-1"},
                "locked": {"locked": True, "value": "do-not-store"},
            },
            conversation_anchor={"type": "match", "key": "usa-vs-eng"},
        ),
        request,
        "user-1",
        repos,
    )

    assert accepted.conversation_id == "conv-existing"
    assert lock.keys == ["anchor:user-1:match:usa-vs-eng"]
    assert repos.committed is True
    plan = repos.created_runs[0][1]["plan"]
    rendered_context = repr(plan["run_context"])
    assert "ctx-1" in rendered_context
    assert "do-not-store" not in rendered_context
    assert "[masked:locked]" in rendered_context
