# Phase 5 — OODA Agent Core: Tools & Prompts

## Task 5.8: Tool Overview (`src/agent/tools/`)

The agent has access to 6 tool categories, implemented as LangChain tools. Each tool is a function decorated with `@tool` that the LLM can invoke during ORIENT/DECIDE reasoning.

### 1. Mastery Tool (`mastery.py`)

**Signature:** `get_mastery(concept_ids: list[str]) → list[dict]`

Queries the `ConceptRepo` to retrieve mastery levels for specified concepts. Returns a list of `{concept_id, name, mastery_level (0-1), last_assessed}`.

**Used by:** ORIENT node to answer "does the student understand the prerequisites of what they're struggling with?"

### 2. Profile Tool (`profile.py`)

**Signature:** `get_or_create_profile(user_id: str) → LearnerProfile`

Fetches the learner profile from the database. If none exists, creates a default profile with empty mastery map, balanced learning style, and default pacing.

**Used by:** ORIENT node to set `state.learner_profile` on first OODA cycle.

### 3. Concept Graph Tool (`concept_graph.py`)

**Signature:** `traverse_prerequisites(concept_id: str, depth: int = 3) → list[dict]`

Calls `concept_graph.queries.get_prerequisite_chain()` to walk the prerequisite DAG. Returns the prerequisite chain up to `depth` levels.

**Used by:** ORIENT node to map which prerequisite concepts might be weak.

### 4. Intervention Tools (`intervention.py`)

**Two functions:**
- `get_intervention_history(user_id: str, limit: int = 20) → list[dict]` — Retrieves past interventions for the user from `InterventionRepo`
- `log_intervention_result(intervention_id: str, was_effective: bool) → dict` — Reports back to the `EffectivenessTracker` for updating Beta posteriors

**Used by:** DECIDE node (history for context) and ACT node (logging for learning).

### 5. Community Insight Tool (`community_insight.py`)

**Signature:** `get_community_insight(concept_id: str) → dict`

Retrieves aggregated peer data from the global wisdom store (Phase 6): common mistake patterns, average time to mastery, effective intervention types for this concept.

**Used by:** ORIENT node to provide comparative context ("most students struggle with X before Y" / "the most effective intervention for this concept is Z").

### 6. Pacing Tool (`pacing.py`)

**Signature:** `adjust_pacing(profile: dict, performance_metrics: dict) → dict`

Returns recommended pacing adjustments:
- `review` — 0.0 (no review needed) to 1.0 (full review recommended)
- `new_content` — recommended difficulty for next challenge
- `break_recommended` — bool, true if engagement is very low

**Used by:** DECIDE node to influence intervention type (e.g., if break_recommended, skip remediation and suggest a break).

---

## Task 5.9: Prompts (`src/agent/prompts/`)

### 1. ORIENT System Prompt (`orient_system.txt`)

```txt
You are an educational diagnostician. Your job is to analyze student
observations and determine:
1. What specific concepts the student is struggling with
2. Why they might be struggling (prerequisite gaps, conceptual confusion, etc.)
3. Their current engagement level
4. How their learner profile should be updated

You have access to the student's current profile and concept mastery state.
Use the provided tools to investigate prerequisite chains and community data.

Always respond with a JSON object containing:
- "struggles": list of concept_ids
- "engagement_score": float 0-1
- "narrative": brief explanation of your reasoning
- "profile_delta": dict of profile fields to update
```

**Design note:** The prompt instructs the LLM to respond with JSON, which the ORIENT node parses. This is more reliable than unstructured text for downstream processing. The `narrative` field serves as the human-readable message.

### 2. DECIDE Context Prompt (`decide_context.txt`)

Used by the DECIDE node (not as a separate LLM call but as context for the Thompson Sampling decision):

```txt
Current diagnosed struggles: {struggles}
Learner engagement: {engagement_score}
Profile learning style: {learning_style}
Available interventions for these concepts: {candidates}

Select the best intervention considering:
1. The student's specific struggle patterns
2. Their learning style preference
3. Whether this is an opportunity to explore new intervention types
4. The community effectiveness data for this concept
```

### 3. ACT System Prompt (`act_system.txt`)

```txt
You are an educational intervention generator. Given an intervention type
and concept, generate a personalized response.

Intervention types:
- hint: A step-by-step hint that guides without giving away the answer
- video_recommendation: Recommend a specific video or section to review
- code_review: Point out specific code issues and suggest improvements
- practice: Generate a practice problem at appropriate difficulty
- encouragement: Motivational message when engagement is low

Always address the student directly and be specific to their situation.
```

### 4. ACT Content Prompt Template

```txt
Generate a {intervention_type} for a student struggling with {concept}.
Student profile: {profile}

The student's recent challenges involved {struggles}.
{extra_context}

Respond in a natural, supportive tone. Be specific — reference the actual
concept and challenge they're working on.
```

### How Prompts Flow

```
OBSERVE → generates observation_summary (not a prompt, a data summary)
ORIENT  → ORIENT_SYSTEM_PROMPT + user prompt with observation + profile + concept state
DECIDE  → no separate LLM call (uses Thompson Sampling), but has context prompt for rationale
ACT     → ACT_SYSTEM_PROMPT + user prompt with intervention type + concept + profile
```
