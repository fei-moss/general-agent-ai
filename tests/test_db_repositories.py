from __future__ import annotations

from sqlalchemy import UniqueConstraint

from app.core.enums import RunStatus
from app.core.models import IdempotencyRecord, Message, ToolCallLog
from app.core.schemas import ChatAccepted


def test_message_model_binds_assistant_message_to_agent_run():
    assert "agent_run_id" in Message.__table__.columns
    assert Message.__table__.columns["agent_run_id"].nullable is True


def test_idempotency_record_has_unique_user_key_contract():
    columns = IdempotencyRecord.__table__.columns

    assert {"user_id", "idempotency_key", "agent_run_id", "request_hash"}.issubset(
        set(columns.keys())
    )
    unique_columns = {
        tuple(constraint.columns.keys())
        for constraint in IdempotencyRecord.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("user_id", "idempotency_key") in unique_columns


def test_idempotency_agent_run_fk_is_deferrable_for_pre_lock_claim():
    agent_run_fk = next(
        fk
        for fk in IdempotencyRecord.__table__.columns["agent_run_id"].foreign_keys
        if fk.column.table.name == "agent_run"
    )

    assert agent_run_fk.deferrable is True
    assert agent_run_fk.initially == "DEFERRED"


def test_chat_accepted_supports_optional_route_type():
    accepted = ChatAccepted(
        conversation_id="conv-1",
        agent_run_id="run-1",
        trace_id="trace-1",
        status=RunStatus.PENDING,
        stream_url="/stream/run-1",
        ws_url="/ws/run-1",
        route_type="realtime",
    )

    assert accepted.model_dump()["route_type"] == "realtime"


def test_tool_call_log_has_attempt_and_timing_fields():
    columns = ToolCallLog.__table__.columns

    assert "attempt" in columns
    assert "started_at" in columns
    assert "finished_at" in columns
