#!/usr/bin/env python3
"""One-time script to build the concept graph from video titles and challenge metadata."""

import asyncio
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.concept_graph.builder import build_concept_graph
from src.db.engine import get_engine, get_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fetch_video_titles(session: AsyncSession) -> list[dict[str, Any]]:
    try:
        result = await session.execute(
            text("SELECT id, title, url FROM ab6_data.challenge_videos LIMIT 500")
        )
        return [
            {"id": str(row[0]), "title": row[1], "url": row[2]}
            for row in result
        ]
    except Exception as e:
        logger.warning(
            "Could not fetch from ab6_data.challenge_videos: %s. Using sample data.", e
        )
        return [
            {"id": "1", "title": "Kinematics - Forward Kinematics - DH Parameters"},
            {"id": "2", "title": "Kinematics - Inverse Kinematics - Jacobian"},
            {"id": "3", "title": "Dynamics - Newton-Euler Formulation"},
        ]


async def main():
    logger.info("Building concept graph...")
    session = await get_session()
    titles = await fetch_video_titles(session)
    result = await build_concept_graph(titles, session)
    logger.info("Concept graph built: %s", result)
    await session.close()


if __name__ == "__main__":
    asyncio.run(main())
