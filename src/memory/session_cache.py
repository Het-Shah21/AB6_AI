import json
import logging
from typing import Any

import redis.asyncio as aioredis

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class SessionCache:
    def __init__(self, redis_client: aioredis.Redis | None = None):
        self._redis = redis_client
        self._settings = get_settings()

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is not None:
            return self._redis
        self._redis = aioredis.from_url(
            self._settings.redis_url,
            decode_responses=True,
        )
        return self._redis

    def _state_key(self, user_id: str) -> str:
        return f"session:{user_id}:state"

    def _events_key(self, user_id: str) -> str:
        return f"session:{user_id}:events"

    def _cooldown_key(self, user_id: str) -> str:
        return f"session:{user_id}:cooldown"

    async def get_state(
        self, user_id: str
    ) -> dict[str, Any] | None:
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
            self._state_key(user_id),
            ttl,
            json.dumps(state, default=str),
        )

    async def push_event(
        self, user_id: str, event: dict[str, Any]
    ) -> None:
        r = await self._get_redis()
        key = self._events_key(user_id)
        await r.lpush(key, json.dumps(event))
        await r.ltrim(key, 0, 99)

    async def pop_events(
        self, user_id: str, count: int = 100
    ) -> list[dict[str, Any]]:
        r = await self._get_redis()
        key = self._events_key(user_id)
        events = []
        for _ in range(count):
            data = await r.rpop(key)
            if data is None:
                break
            try:
                events.append(json.loads(data))
            except json.JSONDecodeError:
                continue
        return events

    async def set_cooldown(
        self, user_id: str, seconds: int = 60
    ) -> None:
        r = await self._get_redis()
        await r.setex(self._cooldown_key(user_id), seconds, "1")

    async def is_cooldown_active(self, user_id: str) -> bool:
        r = await self._get_redis()
        return await r.exists(self._cooldown_key(user_id)) > 0

    async def clear_session(self, user_id: str) -> None:
        r = await self._get_redis()
        await r.delete(
            self._state_key(user_id),
            self._events_key(user_id),
            self._cooldown_key(user_id),
        )
