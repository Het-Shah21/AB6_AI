import json
import logging
from typing import Any

from src.db.repositories.concept_repo import ConceptRepo
from src.llm.provider import get_llm_for_purpose
from src.intervention.effectiveness import calibrate_difficulty

logger = logging.getLogger(__name__)

CHALLENGE_GENERATION_PROMPT = """You are an AI challenge generator for a robotics education platform.
Generate a {challenge_type} challenge for the concept "{concept_name}" at difficulty {difficulty}.

The challenge should:
1. Be appropriate for difficulty {difficulty} (0.0 = easy, 1.0 = hard)
2. Test understanding of the core concept, not memorization
3. Include a clear problem statement
4. Include the correct answer and explanation

Domain: {domain}
Description: {description}

Respond with a JSON object:
For MCQ:
{{
    "type": "mcq",
    "question": "...",
    "options": ["A", "B", "C", "D"],
    "correct_answer": 0,
    "explanation": "..."
}}
For code:
{{
    "type": "code",
    "problem_statement": "...",
    "solution_template": "...",
    "test_cases": [{{"input": "...", "expected_output": "..."}}],
    "explanation": "..."
}}
"""

CRITIQUE_PROMPT = """You are QA reviewer for educational content.
Review this challenge and provide a critique.

Criteria: difficulty (0-1), clarity (0-1), correctness (0-1), helpfulness (0-1)

Return JSON: {{"quality_score": 0.0-1.0, "issues": [...], "suggestions": [...]}}

Challenge:
{challenge}
"""


async def generate_challenge(
    concept_id: str,
    difficulty: float,
    challenge_type: str = "mcq",
    learner_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    concept_repo = ConceptRepo()
    concept_data = await concept_repo.get_with_neighbors(concept_id)
    concept = concept_data.get("concept")
    if concept is None:
        return {"error": f"Concept {concept_id} not found"}

    llm = await get_llm_for_purpose("reasoning")

    prompt = CHALLENGE_GENERATION_PROMPT.format(
        challenge_type=challenge_type,
        concept_name=concept.get("name", concept_id),
        difficulty=difficulty,
        domain=concept.get("domain", ""),
        description=concept.get("name", ""),
    )

    result = await llm.ainvoke([
        {"role": "system", "content": "You are a robotics challenge generator."},
        {"role": "user", "content": prompt},
    ])

    raw = str(result.content)
    try:
        challenge = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            challenge = json.loads(raw[start:end])
        else:
            return {"error": "Failed to parse generated challenge", "raw": raw}

    critique_raw = await llm.ainvoke([
        {
            "role": "system",
            "content": "You are a QA reviewer for educational content.",
        },
        {
            "role": "user",
            "content": CRITIQUE_PROMPT.format(challenge=json.dumps(challenge, indent=2)),
        },
    ])

    try:
        critique = json.loads(str(critique_raw.content))
        quality_score = critique.get("quality_score", 0.5)
        if quality_score < 0.7:
            challenge = await _regenerate_with_feedback(challenge, critique)
    except (json.JSONDecodeError, AttributeError):
        quality_score = 0.7

    challenge["concept_id"] = concept_id
    challenge["difficulty"] = calibrate_difficulty(challenge, concept)
    challenge["quality_score"] = quality_score

    return challenge


async def _regenerate_with_feedback(
    challenge: dict[str, Any],
    critique: dict[str, Any],
) -> dict[str, Any]:
    llm = await get_llm_for_purpose("reasoning")
    result = await llm.ainvoke([
        {"role": "system", "content": "Improve the challenge based on the feedback."},
        {
            "role": "user",
            "content": f"Original: {json.dumps(challenge)}\nFeedback: {json.dumps(critique)}",
        },
    ])
    raw = str(result.content)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return challenge


async def generate_concept_explanation(
    concept_id: str, depth: str = "brief"
) -> str:
    concept_repo = ConceptRepo()
    concept = await concept_repo.get(concept_id)
    if concept is None:
        return f"Concept '{concept_id}' not found."

    llm = await get_llm_for_purpose("primary")
    result = await llm.ainvoke([
        {
            "role": "system",
            "content": f"Explain '{concept.name}' at {depth} depth. "
            "Use LaTeX for formulas: $formula$. Be concise.",
        },
        {
            "role": "user",
            "content": f"Concept: {concept.name}\nDomain: {concept.domain}\n"
            f"Description: {concept.description or ''}",
        },
    ])
    return str(result.content)
