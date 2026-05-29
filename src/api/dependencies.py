import redis.asyncio as aioredis
from fastapi import Request

from src.config.settings import get_settings
from src.db.engine import get_session
from src.ingestion.consumer import RedisStreamConsumer
from src.memory.session_cache import SessionCache


async def get_redis(request: Request) -> aioredis.Redis:
    if not hasattr(request.app.state, "redis"):
        settings = get_settings()
        request.app.state.redis = aioredis.from_url(
            settings.redis_url, decode_responses=True
        )
    return request.app.state.redis


async def get_stream_consumer(
    request: Request,
) -> RedisStreamConsumer:
    redis = await get_redis(request)
    return RedisStreamConsumer(redis)


async def get_session_cache(request: Request) -> SessionCache:
    redis = await get_redis(request)
    return SessionCache(redis)
