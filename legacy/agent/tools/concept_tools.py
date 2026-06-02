from langchain_core.tools import tool

from src.db.repositories.concept_repo import ConceptRepo
from legacy.concept_graph.queries import get_prerequisite_chain


@tool
async def query_concept_graph(concept_id: str, depth: int = 2) -> dict:
    """Get concept prerequisites and dependents up to N levels deep."""
    repo = ConceptRepo()
    return await repo.get_with_neighbors(concept_id, depth)


@tool
async def search_similar_concepts(query: str, top_k: int = 5) -> list[dict]:
    """Semantic search over concept embeddings using pgvector."""
    from legacy.concept_graph.embeddings import generate_embedding

    repo = ConceptRepo()
    embedding = await generate_embedding(query)
    results = await repo.search_similar(embedding, top_k)
    return [
        {"id": c.id, "name": c.name, "domain": c.domain}
        for c in results
    ]


@tool
async def get_prerequisite_chain_tool(concept_id: str) -> list[str]:
    """Get the prerequisite chain for a concept (ordered from foundational to advanced)."""
    return await get_prerequisite_chain(concept_id)
