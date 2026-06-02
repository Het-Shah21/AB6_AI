import logging

from fastapi import APIRouter, Query

from src.db.repositories.concept_repo import ConceptRepo
from legacy.concept_graph.queries import get_prerequisite_chain

logger = logging.getLogger(__name__)
router = APIRouter(tags=["concept-graph"])


@router.get("/concepts/{concept_id}")
async def get_concept(concept_id: str):
    repo = ConceptRepo()
    concept = await repo.get(concept_id)
    if concept is None:
        return {"status": "not_found", "concept_id": concept_id}
    return {
        "id": concept.id,
        "name": concept.name,
        "domain": concept.domain,
        "difficulty": concept.difficulty,
        "source_type": concept.source_type,
    }


@router.get("/concepts/{concept_id}/neighbors")
async def get_concept_neighbors(
    concept_id: str, depth: int = Query(default=2, le=5)
):
    repo = ConceptRepo()
    return await repo.get_with_neighbors(concept_id, depth)


@router.get("/concepts/{concept_id}/prerequisites")
async def get_concept_prerequisites(concept_id: str):
    chain = await get_prerequisite_chain(concept_id)
    return {"concept_id": concept_id, "prerequisites": chain}


@router.get("/concepts/search")
async def search_concepts(
    query: str = Query(min_length=2),
    top_k: int = Query(default=5, le=20),
):
    from legacy.concept_graph.embeddings import generate_embedding

    repo = ConceptRepo()
    embedding = await generate_embedding(query)
    results = await repo.search_similar(embedding, top_k)
    return {
        "query": query,
        "results": [
            {
                "id": c.id,
                "name": c.name,
                "domain": c.domain,
                "difficulty": c.difficulty,
            }
            for c in results
        ],
    }
