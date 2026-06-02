"""Session cache for the mentor.

Two backends:

  - ``MENTOR_SESSION_BACKEND=redis`` (default)  — uses real Redis
  - ``MENTOR_SESSION_BACKEND=memory``           — in-process dict

Both expose ``MentorSessionCache`` with the same async API so the
stages and the API don't have to branch.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from typing import Any

from src.config.settings import get_settings


def _is_memory() -> bool:
    return get_settings().mentor_session_backend == "memory"


def _in_memory_store() -> "_InMemoryStore":
    global _store
    if _store is None:
        _store = _InMemoryStore()
    return _store


class _InMemoryStore:
    """Replacement for the slice of Redis the mentor cache uses."""

    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.lists: dict[str, deque] = defaultdict(deque)
        self.sets: dict[str, set] = defaultdict(set)
        self.hashes: dict[str, dict[str, str]] = defaultdict(dict)
        self.expiry: dict[str, float] = {}

    async def get(self, key: str) -> str | None:
        return self.kv.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.kv[key] = value
        import time
        self.expiry[key] = time.time() + ttl

    async def lpush(self, key: str, value: str) -> None:
        self.lists[key].appendleft(value)

    async def ltrim(self, key: str, start: int, end: int) -> None:
        dq = self.lists[key]
        maxlen = end + 1
        while len(dq) > maxlen:
            dq.pop()

    async def expire(self, key: str, ttl: int) -> None:
        import time
        self.expiry[key] = time.time() + ttl

    async def lrange(self, key: str, start: int, end: int) -> list:
        dq = self.lists[key]
        s = max(0, start)
        e = min(len(dq), end + 1) if end >= 0 else len(dq)
        return list(dq)[s:e]

    async def delete(self, *keys: str) -> None:
        for k in keys:
            self.kv.pop(k, None)
            self.lists.pop(k, None)
            self.sets.pop(k, None)
            self.hashes.pop(k, None)
            self.expiry.pop(k, None)

    async def exists(self, key: str) -> int:
        return 1 if key in self.kv or key in self.lists or key in self.sets else 0

    async def sadd(self, key: str, value: str) -> None:
        self.sets[key].add(value)

    async def srem(self, key: str, value: str) -> None:
        self.sets[key].discard(value)

    async def smembers(self, key: str) -> set:
        return set(self.sets.get(key, set()))

    async def hset(self, key: str, mapping: dict | None = None, **kwargs) -> None:
        h = self.hashes[key]
        if mapping:
            h.update({k: str(v) for k, v in mapping.items()})
        h.update({k: str(v) for k, v in kwargs.items()})

    async def hgetall(self, key: str) -> dict:
        return dict(self.hashes.get(key, {}))


_store: _InMemoryStore | None = None


class MentorSessionCache:
    def __init__(self, redis_client: Any | None = None) -> None:
        self._redis = redis_client

    async def _get_redis(self):
        if self._redis is not None:
            return self._redis
        if _is_memory():
            return _in_memory_store()
        import redis.asyncio as aioredis
        if self._redis is None:
            settings = get_settings()
            self._redis = aioredis.from_url(
                settings.redis_url, decode_responses=True
            )
        return self._redis

    @staticmethod
    def _state_key(user_id: str) -> str:
        return f"mentor:session:{user_id}:state"

    @staticmethod
    def _events_key(user_id: str) -> str:
        return f"mentor:session:{user_id}:events"

    @staticmethod
    def _cooldown_key(user_id: str, intervention_type: str) -> str:
        return f"mentor:cooldown:{user_id}:{intervention_type}"

    async def get_state(self, user_id: str) -> dict | None:
        r = await self._get_redis()
        data = await r.get(self._state_key(user_id))
        if data is None:
            return None
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return None

    async def set_state(self, user_id: str, state: dict, ttl: int = 3600) -> None:
        r = await self._get_redis()
        await r.setex(
            self._state_key(user_id), ttl, json.dumps(state, default=str)
        )

    async def append_event(self, user_id: str, event: dict) -> None:
        r = await self._get_redis()
        key = self._events_key(user_id)
        await r.lpush(key, json.dumps(event, default=str))
        await r.ltrim(key, 0, 999)
        await r.expire(key, 86400)

    async def peek_events(self, user_id: str, count: int = 100) -> list[dict]:
        r = await self._get_redis()
        raw = await r.lrange(self._events_key(user_id), 0, count - 1)
        out: list[dict] = []
        for data in raw:
            try:
                out.append(json.loads(data))
            except json.JSONDecodeError:
                continue
        out.reverse()
        return out

    async def drain_events(self, user_id: str, count: int = 100) -> list[dict]:
        r = await self._get_redis()
        key = self._events_key(user_id)
        raw = await r.lrange(key, 0, count - 1)
        await r.delete(key)
        out: list[dict] = []
        for data in raw:
            try:
                out.append(json.loads(data))
            except json.JSONDecodeError:
                continue
        out.reverse()
        return out

    async def set_cooldown(self, user_id: str, intervention_type: str, seconds: int) -> None:
        r = await self._get_redis()
        await r.setex(self._cooldown_key(user_id, intervention_type), seconds, "1")

    async def is_cooldown_active(self, user_id: str, intervention_type: str) -> bool:
        r = await self._get_redis()
        return await r.exists(self._cooldown_key(user_id, intervention_type)) > 0

    async def clear_session(self, user_id: str) -> None:
        r = await self._get_redis()
        await r.delete(
            self._state_key(user_id),
            self._events_key(user_id),
        )
