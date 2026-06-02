from langchain_core.tools import tool

from src.db.repositories.wisdom_repo import WisdomRepo
from src.db.repositories.benchmark_repo import BenchmarkRepo


@tool
async def query_wisdom(
    concept_id: str, intervention_type: str, profile: dict
) -> dict:
    """Query the global wisdom store for intervention effectiveness stats."""
    repo = WisdomRepo()
    segment = profile.get("profile_segment", {})
    wisdom = await repo.get_or_create(
        concept_id=concept_id,
        intervention_type=intervention_type,
        profile_segment=segment,
    )
    return {
        "concept_id": wisdom.concept_id,
        "intervention_type": wisdom.intervention_type,
        "success_rate": wisdom.success_rate,
        "total_trials": wisdom.total_trials,
        "insight": wisdom.insight_text or "",
    }


@tool
async def query_population_benchmark(concept_id: str) -> dict:
    """Get population-level statistics for comparison."""
    repo = BenchmarkRepo()
    bm = await repo.get(concept_id)
    if bm is None:
        return {"concept_id": concept_id, "available": False}
    return {
        "concept_id": concept_id,
        "avg_mastery": bm.avg_mastery,
        "median_mastery": bm.median_mastery,
        "p25_mastery": bm.p25_mastery,
        "p75_mastery": bm.p75_mastery,
        "avg_attempts": bm.avg_attempts,
        "sample_size": bm.sample_size,
    }
