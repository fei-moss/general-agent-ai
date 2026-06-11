"""Redis Stream event bus.

Redis Stream is the replay source for high-concurrency chat streams. The Redis
entry id is injected into AgentEvent.stream_id after XADD and after replay reads.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from app.core.config import get_settings
from app.core.events import AgentEvent
from app.core.metrics import Metrics

STREAM_PREFIX = "stream:run:"
DEFAULT_BLOCK_MS = 5000


class StreamGapError(RuntimeError):
    """Raised when a replay cursor is older than retained Stream entries."""


def stream_key_for(agent_run_id: str) -> str:
    return f"{STREAM_PREFIX}{agent_run_id}"


class StreamBus:
    """Redis Stream implementation for run events."""

    def __init__(
        self,
        redis_url: str | None = None,
        redis_client: Any | None = None,
        *,
        maxlen: int | None = None,
        block_ms: int = DEFAULT_BLOCK_MS,
        metrics: Metrics | None = None,
    ) -> None:
        settings = get_settings()
        self._redis_url = redis_url or settings.redis_url
        self._client = redis_client
        self._maxlen = maxlen
        self._block_ms = block_ms
        self._metrics = metrics or Metrics()

    def _get_client(self) -> Any:
        if self._client is None:
            import redis.asyncio as redis_asyncio

            self._client = redis_asyncio.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def publish(self, run_id: str, event: AgentEvent) -> AgentEvent:
        client = self._get_client()
        run_id = _normalize_run_id(run_id)
        stream_id = await client.xadd(
            stream_key_for(run_id),
            {"event": event.to_json()},
            maxlen=self._maxlen,
            approximate=True,
        )
        self._metrics.inc_counter("redis_stream_events_total", {"run_id": run_id})
        return event.model_copy(update={"stream_id": _decode(stream_id)})

    async def replay(
        self, run_id: str, after_id: str | None
    ) -> AsyncIterator[AgentEvent]:
        client = self._get_client()
        run_id = _normalize_run_id(run_id)
        key = stream_key_for(run_id)
        await self._ensure_cursor_retained(client, key, after_id)
        min_id = f"({after_id}" if after_id else "-"
        entries = await client.xrange(key, min=min_id, max="+")
        self._metrics.set_gauge(
            "redis_stream_lag_events",
            0,
            {"run_id": run_id},
        )
        for stream_id, fields in entries:
            yield self._decode_entry(stream_id, fields)

    async def subscribe(
        self, run_id: str, after_id: str | None = None
    ) -> AsyncIterator[AgentEvent]:
        run_id = _normalize_run_id(run_id)
        cursor = after_id
        async for event in self.replay(run_id, after_id):
            cursor = event.stream_id
            yield event

        if cursor is None:
            cursor = "$"

        client = self._get_client()
        key = stream_key_for(run_id)
        while True:
            response = await client.xread(
                {key: cursor},
                count=1,
                block=self._block_ms,
            )
            if not response:
                await asyncio.sleep(0)
                continue
            for _, entries in response:
                for stream_id, fields in entries:
                    event = self._decode_entry(stream_id, fields)
                    cursor = event.stream_id
                    yield event

    async def close(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            await self._client.close()
            self._client = None

    async def _ensure_cursor_retained(
        self, client: Any, key: str, after_id: str | None
    ) -> None:
        if after_id is None:
            return
        first_entries = await client.xrange(key, min="-", max="+", count=1)
        if not first_entries:
            return
        first_id = _decode(first_entries[0][0])
        if _compare_stream_ids(after_id, first_id) < 0:
            raise StreamGapError(f"cursor {after_id} is outside retained stream")

    @staticmethod
    def _decode_entry(stream_id: Any, fields: dict[Any, Any]) -> AgentEvent:
        event_json = fields.get("event")
        if event_json is None:
            event_json = fields.get(b"event")
        event = AgentEvent.from_json(_decode(event_json))
        return event.model_copy(update={"stream_id": _decode(stream_id)})


def _decode(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _normalize_run_id(run_id_or_channel: str) -> str:
    if run_id_or_channel.startswith("run:"):
        return run_id_or_channel.removeprefix("run:")
    return run_id_or_channel


def _compare_stream_ids(left: str, right: str) -> int:
    left_ms, left_seq = (int(part) for part in left.split("-", 1))
    right_ms, right_seq = (int(part) for part in right.split("-", 1))
    if left_ms != right_ms:
        return (left_ms > right_ms) - (left_ms < right_ms)
    return (left_seq > right_seq) - (left_seq < right_seq)
