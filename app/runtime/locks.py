"""Redis-backed conversation locks and run leases."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings


_LOCK_RENEW_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('expire', KEYS[1], tonumber(ARGV[2]))
end
return 0
"""

_LOCK_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""

_RUN_RENEW_SCRIPT = """
local raw = redis.call('get', KEYS[1])
if not raw then
  return 0
end
local payload = cjson.decode(raw)
if payload['runner_id'] ~= ARGV[1] then
  return 0
end
payload['last_seen_at'] = tonumber(ARGV[2])
local ttl = tonumber(payload['ttl_s'])
if not ttl or ttl <= 0 then
  return 0
end
redis.call('set', KEYS[1], cjson.encode(payload), 'EX', ttl)
return 1
"""

_RUN_RELEASE_SCRIPT = """
local raw = redis.call('get', KEYS[1])
if not raw then
  return 0
end
local payload = cjson.decode(raw)
if payload['runner_id'] == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


def _decode(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


class _RedisBacked:
    def __init__(
        self, redis_url: str | None = None, redis_client: Any | None = None
    ) -> None:
        settings = get_settings()
        self._redis_url = redis_url or settings.redis_url
        self._client = redis_client

    def _get_client(self) -> Any:
        if self._client is None:
            import redis.asyncio as redis_asyncio

            self._client = redis_asyncio.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client


@dataclass
class LockLease:
    client: Any
    key: str
    owner: str
    ttl_s: int

    async def renew(self) -> bool:
        result = await self.client.eval(
            _LOCK_RENEW_SCRIPT,
            1,
            self.key,
            self.owner,
            self.ttl_s,
        )
        return bool(result)

    async def release(self) -> bool:
        result = await self.client.eval(
            _LOCK_RELEASE_SCRIPT,
            1,
            self.key,
            self.owner,
        )
        return bool(result)


class ConversationLock(_RedisBacked):
    """Single-conversation lock based on Redis SET NX EX."""

    async def acquire(
        self, conversation_id: str, owner: str, ttl_s: int
    ) -> LockLease | None:
        client = self._get_client()
        key = f"lock:conversation:{conversation_id}"
        ok = await client.set(key, owner, nx=True, ex=ttl_s)
        if not ok:
            return None
        return LockLease(client=client, key=key, owner=owner, ttl_s=ttl_s)


class RunLease(_RedisBacked):
    """Heartbeat lease for detecting orphan RUNNING realtime runs."""

    def __init__(
        self, redis_url: str | None = None, redis_client: Any | None = None
    ) -> None:
        super().__init__(redis_url=redis_url, redis_client=redis_client)
        self._owner_by_run: dict[str, str] = {}

    async def start(self, run_id: str, runner_id: str, ttl_s: int) -> None:
        now = time.time()
        payload = json.dumps(
            {
                "runner_id": runner_id,
                "ttl_s": ttl_s,
                "started_at": now,
                "last_seen_at": now,
            },
            sort_keys=True,
        )
        self._owner_by_run[run_id] = runner_id
        await self._get_client().set(self._key(run_id), payload, ex=ttl_s)

    async def renew(self, run_id: str) -> bool:
        runner_id = self._owner_by_run.get(run_id)
        if runner_id is None:
            return False
        client = self._get_client()
        key = self._key(run_id)
        result = await client.eval(
            _RUN_RENEW_SCRIPT,
            1,
            key,
            runner_id,
            time.time(),
        )
        return bool(result)

    async def release(self, run_id: str) -> bool:
        runner_id = self._owner_by_run.pop(run_id, None)
        if runner_id is None:
            return False
        result = await self._get_client().eval(
            _RUN_RELEASE_SCRIPT,
            1,
            self._key(run_id),
            runner_id,
        )
        return bool(result)

    async def is_alive(self, run_id: str) -> bool:
        return await self._get_client().get(self._key(run_id)) is not None

    @staticmethod
    def _key(run_id: str) -> str:
        return f"run:{run_id}:lease"
