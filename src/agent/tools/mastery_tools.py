from langchain_core.tools import tool

from src.db.repositories.learner_profile_repo import LearnerProfileRepo
from src.db.repositories.concept_repo import ConceptRepo


@tool
async def query_mastery(user_id: str, concept_id: str) -> dict:
    """Get the learner's mastery level for a specific concept."""
    repo = LearnerProfileRepo()
    profile = await repo.get(user_id)
    if profile is None:
        return {"mastery": 0.0, "concept_id": concept_id}
    mastery_map = profile.mastery_map or {}
    concept_data = mastery_map.get(concept_id, {})
    if isinstance(concept_data, dict):
        return {
            "mastery": concept_data.get("mastery", 0.0),
            "concept_id": concept_id,
            "last_updated": str(concept_data.get("last_updated", "")),
        }
    return {"mastery": float(concept_data), "concept_id": concept_id}


@tool
async def get_prior_baseline(user_id: str) -> dict:
    """Fetch the user's historical baseline from the old recorded database."""
    repo = LearnerProfileRepo()
    profile = await repo.get(user_id)
    if profile is None:
        return {"baseline": {}}
    return {"baseline": profile.prior_baseline or {}}
