from langchain_core.tools import tool

from src.db.repositories.concept_repo import ConceptRepo
from src.intervention.generator import (
    generate_concept_explanation,
    generate_challenge,
)
from src.intervention.selector import (
    find_best_video_for_concept,
)


@tool
async def generate_explanation(concept_id: str, depth: str = "brief") -> str:
    """Generate a concept explanation (theory, formulas, intuition)."""
    return await generate_concept_explanation(concept_id, depth)


@tool
async def generate_challenge_tool(
    concept_id: str, difficulty: float, challenge_type: str
) -> dict:
    """Generate a new challenge for the given concept."""
    return await generate_challenge(
        concept_id=concept_id,
        difficulty=difficulty,
        challenge_type=challenge_type,
        learner_context={},
    )


@tool
async def recommend_video(concept_id: str, user_id: str) -> dict:
    """Find the most relevant video for a concept, with timestamp."""
    result = await find_best_video_for_concept(concept_id)
    return result or {
        "concept_id": concept_id,
        "found": False,
        "message": "No video found for this concept.",
    }
