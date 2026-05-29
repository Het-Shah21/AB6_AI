import json
import logging
from typing import Any

import redis.asyncio as aioredis

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class RedisStreamConsumer:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.settings = get_settings()

    async def push_observation(
        self, event: dict[str, Any]
    ) -> str:
        return await self.redis.xadd(
            self.settings.redis_stream_observation,
            {"data": json.dumps(event)},
            maxlen=10000,
        )

    async def push_telemetry(
        self, event: dict[str, Any]
    ) -> str:
        return await self.redis.xadd(
            self.settings.redis_stream_telemetry,
            {"data": json.dumps(event)},
            maxlen=5000,
        )

    async def push_domain_event(
        self, event: dict[str, Any]
    ) -> str:
        return await self.redis.xadd(
            self.settings.redis_stream_domain_events,
            {"data": json.dumps(event)},
            maxlen=10000,
        )

    async def read_events(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 100,
        block_ms: int = 1000,
    ) -> list[dict[str, Any]]:
        try:
            result = await self.redis.xreadgroup(
                group,
                consumer,
                {stream: ">"},
                count=count,
                block=block_ms,
            )
        except aioredis.ResponseError:
            await self._ensure_group(stream, group)
            return []
        events = []
        if result:
            for stream_name, messages in result:
                for msg_id, msg_data in messages:
                    decoded = json.loads(msg_data[b"data"].decode())
                    decoded["_stream"] = stream_name.decode()
                    decoded["_msg_id"] = msg_id.decode()
                    events.append(decoded)
        return events

    async def ack(self, stream: str, group: str, msg_id: str) -> None:
        await self.redis.xack(stream, group, msg_id)

    async def _ensure_group(
        self, stream: str, group: str
    ) -> None:
        try:
            await self.redis.xgroup_create(stream, group, id="$", mkstream=True)
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
