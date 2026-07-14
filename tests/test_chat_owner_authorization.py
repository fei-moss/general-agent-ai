from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routers import chat
from app.api.routers.conversations import _assert_owner
from app.api.routers.runs import get_run_status
from app.core.enums import RunStatus
from app.core.schemas import ChatRequest


async def test_batch_cross_owner_conversation_is_rejected_before_side_effects():
    class _Repos:
        async def get_conversation(self, conversation_id):
            return SimpleNamespace(id=conversation_id, user_id="wallet-owner")

        async def get_idempotency_record(self, *args, **kwargs):
            raise AssertionError("idempotency must not run before owner check")

        async def ensure_conversation(self, *args, **kwargs):
            raise AssertionError("conversation reuse must not run after owner denial")

        async def create_queued_task(self, *args, **kwargs):
            raise AssertionError("task creation must not run after owner denial")

        async def commit(self):
            raise AssertionError("commit must not run after owner denial")

    request = SimpleNamespace(
        headers={"idempotency-key": "cross-owner"},
        state=SimpleNamespace(trace_id="trace-1"),
        app=SimpleNamespace(state=SimpleNamespace()),
    )

    with pytest.raises(HTTPException) as exc:
        await chat.create_chat(
            ChatRequest(
                message="hello",
                conversation_id="conv-other",
                metadata={"mode": "batch"},
            ),
            request,
            "wallet-caller",
            _Repos(),
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "无权访问该会话"


def test_conversation_null_owner_is_denied():
    with pytest.raises(HTTPException) as exc:
        _assert_owner(None, "wallet-caller")

    assert exc.value.status_code == 403


@pytest.mark.parametrize(
    ("conversation", "status_code"),
    [
        (None, 404),
        (SimpleNamespace(user_id=None), 403),
        (SimpleNamespace(user_id="wallet-other"), 403),
    ],
)
async def test_run_status_fails_closed_on_parent_conversation(
    conversation, status_code: int
):
    class _Repos:
        async def get_run(self, run_id):
            return SimpleNamespace(
                id=run_id,
                conversation_id="conv-1",
                status=RunStatus.RUNNING,
                intent=None,
                error=None,
            )

        async def get_conversation(self, conversation_id):
            return conversation

    with pytest.raises(HTTPException) as exc:
        await get_run_status("run-1", "wallet-caller", _Repos())

    assert exc.value.status_code == status_code
