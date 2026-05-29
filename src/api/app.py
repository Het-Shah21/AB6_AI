import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import (
    events_router,
    telemetry_router,
    interventions_router,
    agent_router,
    concept_graph_router,
)
from src.config.settings import get_settings
from src.db.engine import close_engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.redis = aioredis.from_url(
        settings.redis_url, decode_responses=True
    )
    logger.info("AB6 AI Agent API started")
    yield
    await close_engine()
    if hasattr(app.state, "redis"):
        await app.state.redis.close()
    logger.info("AB6 AI Agent API shut down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AB6 AI Agent API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(events_router, prefix="/api/v1/ai")
    app.include_router(telemetry_router, prefix="/api/v1/ai")
    app.include_router(interventions_router, prefix="/api/v1/ai")
    app.include_router(agent_router, prefix="/api/v1/ai")
    app.include_router(concept_graph_router, prefix="/api/v1/ai")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "ab6-ai-agent"}

    return app


app = create_app()
