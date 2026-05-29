import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_session
from src.db.models.ai_concept import AIConcept
from src.db.models.ai_concept_edge import AIConceptEdge
from src.db.models.ai_concept_mapping import AIConceptMapping


class ConceptRepo:
    def __init__(self, session: AsyncSession | None = None):
        self._session = session

    async def _get_session(self) -> AsyncSession:
        if self._session is not None:
            return self._session
        return await get_session()

    async def get(self, concept_id: str) -> AIConcept | None:
        sess = await self._get_session()
        result = await sess.execute(
            select(AIConcept).where(
                AIConcept.id == concept_id
            )
        )
        return result.scalar_one_or_none()

    async def get_with_neighbors(
        self, concept_id: str, depth: int = 2
    ) -> dict[str, Any]:
        sess = await self._get_session()
        concept = await self.get(concept_id)
        if concept is None:
            return {"concept": None, "prerequisites": [], "dependents": []}

        prereq_result = await sess.execute(
            text("""
                WITH RECURSIVE prereq_tree AS (
                    SELECT from_concept_id, to_concept_id, 1 AS level
                    FROM ab6_learning_data.ai_concept_edges
                    WHERE to_concept_id = :concept_id
                    UNION ALL
                    SELECT e.from_concept_id, e.to_concept_id, pt.level + 1
                    FROM ab6_learning_data.ai_concept_edges e
                    JOIN prereq_tree pt ON e.to_concept_id = pt.from_concept_id
                    WHERE pt.level < :depth
                )
                SELECT DISTINCT from_concept_id FROM prereq_tree
            """),
            {"concept_id": concept_id, "depth": depth},
        )
        prereq_ids = [row[0] for row in prereq_result]

        dep_result = await sess.execute(
            text("""
                WITH RECURSIVE dep_tree AS (
                    SELECT from_concept_id, to_concept_id, 1 AS level
                    FROM ab6_learning_data.ai_concept_edges
                    WHERE from_concept_id = :concept_id
                    UNION ALL
                    SELECT e.from_concept_id, e.to_concept_id, dt.level + 1
                    FROM ab6_learning_data.ai_concept_edges e
                    JOIN dep_tree dt ON e.from_concept_id = dt.to_concept_id
                    WHERE dt.level < :depth
                )
                SELECT DISTINCT to_concept_id FROM dep_tree
            """),
            {"concept_id": concept_id, "depth": depth},
        )
        dep_ids = [row[0] for row in dep_result]

        prereqs = []
        for pid in prereq_ids:
            c = await self.get(pid)
            if c:
                prereqs.append(
                    {"id": c.id, "name": c.name, "domain": c.domain}
                )

        dependents = []
        for did in dep_ids:
            c = await self.get(did)
            if c:
                dependents.append(
                    {"id": c.id, "name": c.name, "domain": c.domain}
                )

        return {
            "concept": {
                "id": concept.id,
                "name": concept.name,
                "domain": concept.domain,
                "difficulty": concept.difficulty,
            },
            "prerequisites": prereqs,
            "dependents": dependents,
        }

    async def search_similar(
        self, embedding: list[float], top_k: int = 5
    ) -> list[AIConcept]:
        sess = await self._get_session()
        emb_str = "[" + ",".join(str(v) for v in embedding) + "]"
        result = await sess.execute(
            text("""
                SELECT id, name, domain, difficulty, description
                FROM ab6_learning_data.ai_concepts
                ORDER BY embedding <=> :emb::vector
                LIMIT :top_k
            """),
            {"emb": emb_str, "top_k": top_k},
        )
        return [
            AIConcept(
                id=row[0],
                name=row[1],
                domain=row[2],
                difficulty=row[3],
                description=row[4],
            )
            for row in result
        ]

    async def get_prerequisite_chain(
        self, concept_id: str
    ) -> list[str]:
        sess = await self._get_session()
        result = await sess.execute(
            text("""
                WITH RECURSIVE chain AS (
                    SELECT from_concept_id, to_concept_id, 1 AS level
                    FROM ab6_learning_data.ai_concept_edges
                    WHERE to_concept_id = :cid AND edge_type = 'prerequisite'
                    UNION ALL
                    SELECT e.from_concept_id, e.to_concept_id, c.level + 1
                    FROM ab6_learning_data.ai_concept_edges e
                    JOIN chain c ON e.to_concept_id = c.from_concept_id
                    WHERE e.edge_type = 'prerequisite'
                )
                SELECT DISTINCT from_concept_id FROM chain ORDER BY level DESC
            """),
            {"cid": concept_id},
        )
        return [row[0] for row in result]
