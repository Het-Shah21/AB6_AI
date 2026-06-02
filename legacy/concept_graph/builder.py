import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from legacy.concept_graph.models import ConceptNode, ConceptEdge
from legacy.concept_graph.embeddings import (
    generate_embeddings_batch,
    cosine_similarity,
)
from src.db.engine import get_session
from src.llm.provider import get_llm_for_purpose

logger = logging.getLogger(__name__)

CONCEPT_EXTRACTION_PROMPT = """You are a robotics curriculum designer.
Given these video/challenge titles from a robotics course, extract atomic concepts.
For each concept, provide:
1. A unique ID using dot notation (e.g., "kinematics.forward.dh_parameters")
2. A human-readable name
3. The domain it belongs to
4. A difficulty rating from 0.0 (easy) to 1.0 (hard)

Return a JSON array of objects with keys: id, name, domain, difficulty

Titles:
{titles}
"""

EDGE_INFERENCE_PROMPT = """Given two concepts from a robotics curriculum where A appears before B,
determine if A is a prerequisite for B.

Concept A: {concept_a} (appears earlier in curriculum)
Concept B: {concept_b} (appears later in curriculum)

Respond with JSON: {{"is_prerequisite": true/false, "confidence": 0.0-1.0, "rationale": "..."}}
"""


async def build_concept_graph(
    video_titles: list[dict[str, Any]],
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    sess = session or await get_session()
    titles_text = json.dumps(
        [t.get("title", "") for t in video_titles], indent=2
    )

    llm = await get_llm_for_purpose("reasoning")
    result = await llm.ainvoke(
        [
            {
                "role": "system",
                "content": CONCEPT_EXTRACTION_PROMPT.format(
                    titles=titles_text
                ),
            },
            {
                "role": "user",
                "content": "Extract concepts from these titles.",
            },
        ]
    )
    raw = str(result.content)
    concepts_data = _parse_llm_json(raw)

    concepts = []
    for cd in concepts_data:
        concept = ConceptNode(
            id=cd.get("id", ""),
            name=cd.get("name", ""),
            domain=cd.get("domain", ""),
            difficulty=cd.get("difficulty", 0.5),
            source_type="video_title",
        )
        concepts.append(concept)

    concept_texts = [
        f"{c.name} - {c.domain} - robotics concept"
        for c in concepts
    ]
    embeddings = await generate_embeddings_batch(concept_texts)

    deduped = _deduplicate_concepts(concepts, embeddings, threshold=0.92)

    for concept, emb in zip(deduped, embeddings):
        emb_str = "[" + ",".join(str(v) for v in emb) + "]"
        await sess.execute(
            text("""
                INSERT INTO ab6_learning_data.ai_concepts
                    (id, name, domain, difficulty, embedding, source_type)
                VALUES (:id, :name, :domain, :difficulty, :emb::vector, :source)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    domain = EXCLUDED.domain,
                    difficulty = EXCLUDED.difficulty,
                    embedding = EXCLUDED.embedding
            """),
            {
                "id": concept.id,
                "name": concept.name,
                "domain": concept.domain,
                "difficulty": concept.difficulty,
                "emb": emb_str,
                "source": concept.source_type,
            },
        )

    edges = await _infer_edges(deduped)

    for edge in edges:
        await sess.execute(
            text("""
                INSERT INTO ab6_learning_data.ai_concept_edges
                    (from_concept_id, to_concept_id, edge_type, weight, source)
                VALUES (:from_id, :to_id, :edge_type, :weight, :source)
                ON CONFLICT (from_concept_id, to_concept_id, edge_type)
                DO NOTHING
            """),
            {
                "from_id": edge.from_concept_id,
                "to_id": edge.to_concept_id,
                "edge_type": edge.edge_type,
                "weight": edge.weight,
                "source": edge.source,
            },
        )

    await sess.commit()
    logger.info(
        "Concept graph built: %d concepts, %d edges",
        len(deduped),
        len(edges),
    )

    return {
        "concepts_count": len(deduped),
        "edges_count": len(edges),
    }


def _parse_llm_json(raw: str) -> list[dict[str, Any]]:
    try:
        start = raw.index("[")
        end = raw.rindex("]") + 1
        return json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        logger.warning("Failed to parse LLM JSON, returning empty")
        return []


def _deduplicate_concepts(
    concepts: list[ConceptNode],
    embeddings: list[list[float]],
    threshold: float = 0.92,
) -> list[ConceptNode]:
    if len(concepts) <= 1:
        return concepts
    keep = [True] * len(concepts)
    for i in range(len(concepts)):
        if not keep[i]:
            continue
        for j in range(i + 1, len(concepts)):
            if not keep[j]:
                continue
            sim = cosine_similarity(embeddings[i], embeddings[j])
            if sim >= threshold:
                keep[j] = False
    return [c for c, k in zip(concepts, keep) if k]


async def _infer_edges(
    concepts: list[ConceptNode],
) -> list[ConceptEdge]:
    edges: list[ConceptEdge] = []
    llm = await get_llm_for_purpose("primary")

    for i in range(len(concepts) - 1):
        for j in range(i + 1, len(concepts)):
            prompt = EDGE_INFERENCE_PROMPT.format(
                concept_a=f"{concepts[i].name} ({concepts[i].id})",
                concept_b=f"{concepts[j].name} ({concepts[j].id})",
            )
            result = await llm.ainvoke(
                [
                    {
                        "role": "system",
                        "content": "You are a curriculum designer. Determine prerequisite relationships.",
                    },
                    {"role": "user", "content": prompt},
                ]
            )
            raw = str(result.content)
            try:
                parsed = json.loads(raw)
                if parsed.get("is_prerequisite"):
                    edges.append(
                        ConceptEdge(
                            from_concept_id=concepts[i].id,
                            to_concept_id=concepts[j].id,
                            edge_type="prerequisite",
                            weight=parsed.get("confidence", 0.8),
                        )
                    )
            except (json.JSONDecodeError, KeyError):
                continue

    return edges
