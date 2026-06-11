from __future__ import annotations

import json

from tests.harness_fakes import FakeConversationLock, FakeIdempotencyStore


async def test_conversation_lock_returns_none_when_busy():
    lock = FakeConversationLock(busy=True)

    lease = await lock.acquire("conv-1", "run-1", 30)

    assert lease is None
    assert lock.acquired == []


async def test_idempotency_key_returns_existing_run():
    store = FakeIdempotencyStore()
    response = {"agent_run_id": "run-1", "status": "RUNNING"}
    await store.create("user-1", "key-1", "hash-1", "run-1", response)

    record = await store.get("user-1", "key-1")

    assert record is not None
    assert record.request_hash == "hash-1"
    assert record.response == response


def test_chat_request_hash_is_stable_for_metadata_order():
    from app.api.idempotency import chat_request_hash

    first = chat_request_hash(
        message="hello",
        conversation_id="conv-1",
        metadata={"b": 2, "a": 1},
    )
    second = chat_request_hash(
        message="hello",
        conversation_id="conv-1",
        metadata={"a": 1, "b": 2},
    )

    assert first == second


async def test_redis_conversation_lock_uses_nx_and_ttl():
    from app.runtime.locks import ConversationLock

    class _Redis:
        def __init__(self) -> None:
            self.values = {}
            self.expirations = {}

        async def set(self, key, value, nx=False, ex=None):
            if nx and key in self.values:
                return False
            self.values[key] = value
            self.expirations[key] = ex
            return True

        async def get(self, key):
            return self.values.get(key)

        async def expire(self, key, ex):
            self.expirations[key] = ex
            return True

        async def delete(self, key):
            self.values.pop(key, None)
            return 1

        async def eval(self, script, numkeys, key, owner, ttl=None):
            if "expire" in script.lower():
                if self.values.get(key) == owner:
                    self.expirations[key] = ttl
                    return 1
                return 0
            if self.values.get(key) == owner:
                self.values.pop(key, None)
                return 1
            return 0

    redis = _Redis()
    lock = ConversationLock(redis_client=redis)

    lease = await lock.acquire("conv-1", "run-1", ttl_s=30)
    busy = await lock.acquire("conv-1", "run-2", ttl_s=30)

    assert lease is not None
    assert busy is None
    assert redis.expirations["lock:conversation:conv-1"] == 30
    await lease.renew()
    await lease.release()
    assert "lock:conversation:conv-1" not in redis.values


async def test_lock_release_is_atomic_and_does_not_delete_new_owner_after_expiry():
    from app.runtime.locks import LockLease

    class _Redis:
        def __init__(self) -> None:
            self.values = {"lock:conversation:conv-1": "run-1"}
            self.gets = 0

        async def get(self, key):
            self.gets += 1
            if self.gets == 1:
                self.values[key] = "run-2"
                return "run-1"
            return self.values.get(key)

        async def delete(self, key):
            self.values.pop(key, None)
            return 1

        async def eval(self, script, numkeys, key, owner, *args):
            self.values[key] = "run-2"
            if self.values.get(key) == owner:
                self.values.pop(key, None)
                return 1
            return 0

    redis = _Redis()
    lease = LockLease(
        client=redis,
        key="lock:conversation:conv-1",
        owner="run-1",
        ttl_s=30,
    )

    await lease.release()

    assert redis.values["lock:conversation:conv-1"] == "run-2"


async def test_run_lease_tracks_liveness_and_release():
    from app.runtime.locks import RunLease

    class _Redis:
        def __init__(self) -> None:
            self.values = {}
            self.expirations = {}

        async def set(self, key, value, ex=None):
            self.values[key] = value
            self.expirations[key] = ex
            return True

        async def get(self, key):
            return self.values.get(key)

        async def expire(self, key, ex):
            return key in self.values

        async def delete(self, key):
            self.values.pop(key, None)
            self.expirations.pop(key, None)
            return 1

        async def eval(self, script, numkeys, key, owner, *args):
            current = self.values.get(key)
            if current is None:
                return 0
            payload = json.loads(current)
            if payload.get("runner_id") != owner:
                return 0
            if "del" in script.lower():
                self.values.pop(key, None)
                self.expirations.pop(key, None)
                return 1
            payload["last_seen_at"] = args[0]
            self.values[key] = json.dumps(payload, sort_keys=True)
            self.expirations[key] = payload["ttl_s"]
            return 1

    redis = _Redis()
    lease = RunLease(redis_client=redis)

    await lease.start("run-1", "runner-1", ttl_s=30)
    assert await lease.is_alive("run-1") is True
    await lease.release("run-1")
    assert await lease.is_alive("run-1") is False


async def test_run_lease_renew_without_local_owner_does_not_create_immortal_lease():
    from app.runtime.locks import RunLease

    class _Redis:
        def __init__(self) -> None:
            self.values = {}
            self.expirations = {}

        async def set(self, key, value, ex=None):
            self.values[key] = value
            self.expirations[key] = ex
            return True

        async def get(self, key):
            return self.values.get(key)

        async def delete(self, key):
            self.values.pop(key, None)
            self.expirations.pop(key, None)
            return 1

    redis = _Redis()
    starter = RunLease(redis_client=redis)
    renewer = RunLease(redis_client=redis)

    await starter.start("run-1", "runner-1", ttl_s=30)
    await renewer.renew("run-1")

    assert redis.expirations["run:run-1:lease"] == 30
    assert json.loads(redis.values["run:run-1:lease"])["ttl_s"] == 30
