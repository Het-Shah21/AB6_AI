import json
import logging

import redis.asyncio as aioredis
from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import Worker as ARQWorker, WorkerSettings

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


async def process_observation(ctx: dict, event_data: str) -> None:
    logger.info("Processing observation: %s", event_data[:100])


async def process_telemetry(ctx: dict, event_data: str) -> None:
    logger.info("Processing telemetry: %s", event_data[:100])


async def process_domain_event(ctx: dict, event_data: str) -> None:
    logger.info("Processing domain event: %s", event_data[:100])


class WorkerSettings:
    functions = [
        process_observation,
        process_telemetry,
        process_domain_event,
    ]
    redis_settings = RedisSettings.from_dsn(
        get_settings().redis_url
    )
    keep_result = 60
    poll_delay = 0.5
    max_tasks = 10
