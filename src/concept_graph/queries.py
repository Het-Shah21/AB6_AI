from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_session


async def get_prerequisite_chain(
    concept_id: str, session: AsyncSession | None = None
) -> list[dict[str, Any]]:
    sess = session or await get_session()
    result = await sess.execute(
        text("""
            WITH RECURSIVE chain AS (
                SELECT from_concept_id, 1 AS level
                FROM ab6_learning_data.ai_concept_edges
                WHERE to_concept_id = :cid AND edge_type = 'prerequisite'
                UNION ALL
                SELECT e.from_concept_id, c.level + 1
                FROM ab6_learning_data.ai_concept_edges e
                JOIN chain c ON e.to_concept_id = c.from_concept_id
                WHERE e.edge_type = 'prerequisite'
            )
            SELECT DISTINCT c.from_concept_id, ac.name, ac.domain, c.level
            FROM chain c
            JOIN ab6_learning_data.ai_concepts ac ON ac.id = c.from_concept_id
            ORDER BY c.level DESC
        """),
        {"cid": concept_id},
    )
    return [
        {"id": row[0], "name": row[1], "domain": row[2], "depth": row[3]}
        for row in result
    ]


async def get_concept_learning_path(
    concept_id: str, session: AsyncSession | None = None
) -> list[dict[str, Any]]:
    chain = await get_prerequisite_chain(concept_id, session)
    chain.reverse()
    return chain


async def find_unmastered_prerequisites(
    concept_id: str,
    mastered_concepts: set[str],
    session: AsyncSession | None = None,
) -> list[str]:
    chain = await get_prerequisite_chain(concept_id, session)
    return [
        c["id"] for c in chain if c["id"] not in mastered_concepts
    ]
