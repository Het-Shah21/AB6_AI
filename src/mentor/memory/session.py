"""Redis-backed session cache for the mentor.

Differences from the legacy session_cache.py:
  - events are append-only (LPUSH + LTRIM, not destructive pop)
  - peek_events returns without consuming
  - cooldown key is a per-(user, intervention_type) tombstone
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class MentorSessionCache:
    def __init__(self, redis_client: aioredis.Redis | None = None) -> None:
        self._redis = redis_client
        self._settings = get_settings()

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is not None:
            return self._redis
        self._redis = aioredis.from_url(
            self._settings.redis_url, decode_responses=True
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

    async def get_state(self, user_id: str) -> dict[str, Any] | None:
        r = await self._get_redis()
        data = await r.get(self._state_key(user_id))
        if data is None:
            return None
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return None

    async def set_state(
        self, user_id: str, state: dict[str, Any], ttl: int = 3600
    ) -> None:
        r = await self._get_redis()
        await r.setex(
            self._state_key(user_id), ttl, json.dumps(state, default=str)
        )

    async def append_event(self, user_id: str, event: dict[str, Any]) -> None:
        r = await self._get_redis()
        key = self._events_key(user_id)
        await r.lpush(key, json.dumps(event, default=str))
        await r.ltrim(key, 0, 999)
        await r.expire(key, 86400)

    async def peek_events(
        self, user_id: str, count: int = 100
    ) -> list[dict[str, Any]]:
        """Read without consuming."""
        r = await self._get_redis()
        key = self._events_key(user_id)
        raw = await r.lrange(key, 0, count - 1)
        out: list[dict[str, Any]] = []
        for data in raw:
            try:
                out.append(json.loads(data))
            except json.JSONDecodeError:
                continue
        out.reverse()  # chronological
        return out

    async def drain_events(self, user_id: str, count: int = 100) -> list[dict[str, Any]]:
        """Atomic read-and-clear."""
        r = await self._get_redis()
        key = self._events_key(user_id)
        async with r.pipeline(transaction=True) as pipe:
            pipe.lrange(key, 0, count - 1)
            pipe.delete(key)
            raw, _ = await pipe.execute()
        out: list[dict[str, Any]] = []
        for data in raw:
            try:
                out.append(json.loads(data))
            except json.JSONDecodeError:
                continue
        out.reverse()
        return out

    async def set_cooldown(
        self, user_id: str, intervention_type: str, seconds: int
    ) -> None:
        r = await self._get_redis()
        await r.setex(self._cooldown_key(user_id, intervention_type), seconds, "1")

    async def is_cooldown_active(
        self, user_id: str, intervention_type: str
    ) -> bool:
        r = await self._get_redis()
        return await r.exists(self._cooldown_key(user_id, intervention_type)) > 0

    async def clear_session(self, user_id: str) -> None:
        r = await self._get_redis()
        await r.delete(
            self._state_key(user_id),
            self._events_key(user_id),
        )
