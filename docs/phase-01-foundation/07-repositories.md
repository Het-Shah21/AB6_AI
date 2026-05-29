# Task 1.7 — Repositories: All 5 Data Access Layers

## System Design Reference

Master System Design, "Data Layer — Repository Pattern". The design specified a repository layer between the OODA agent and the ORM models, providing clear CRUD interfaces while abstracting SQLAlchemy details.

---

## Repo 1: `LearnerProfileRepo` (`src/db/repositories/learner_profile_repo.py`)

### Purpose

Reads and writes `AILearnerProfile` records. Used by ORIENT (to load learner state), ACT (to append interventions), and effectiveness tracking (to update mastery).

### Line-by-Line

```python
import uuid
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.engine import get_session
from src.db.models.ai_learner_profile import AILearnerProfile
```

Imports:
- `uuid` — For converting string user_ids to UUID objects
- `select` — SQLAlchemy 2.0's `SELECT` statement builder
- `AsyncSession` — Type hint for the async session
- `get_session` — Creates a new session from the global engine
- `AILearnerProfile` — The ORM model this repo wraps

```python
class LearnerProfileRepo:
    def __init__(self, session: AsyncSession | None = None):
        self._session = session
```

**Constructor accepts an optional session.** If the caller already has a session (e.g., within a transaction), they can pass it in. Otherwise, `None` means the repo creates its own session per operation.

**Design decision:** This enables two usage patterns:
1. Quick read/write: `repo = LearnerProfileRepo()` — auto session
2. Transactional: share a session across multiple repo calls for atomic commits

```python
    async def _get_session(self) -> AsyncSession:
        if self._session is not None:
            return self._session
        return await get_session()
```

**Internal session resolver.** Returns the injected session or creates a new one. This is called by every public method instead of calling `get_session()` directly, ensuring consistent session handling.

```python
    async def get(self, user_id: str) -> AILearnerProfile | None:
        session = await self._get_session()
        result = await session.execute(
            select(AILearnerProfile).where(
                AILearnerProfile.user_id == uuid.UUID(user_id)
            )
        )
        return result.scalar_one_or_none()
```

**Get profile by user_id:**
1. Gets/resolves session
2. `session.execute(select(...).where(...))` — Async query execution. SQLAlchemy builds a `SELECT * FROM ai_learner_profiles WHERE user_id = $1` query.
3. `uuid.UUID(user_id)` — Converts the string to a UUID object for the DB comparison.
4. `scalar_one_or_none()` — Returns the first matching row as an ORM object, or `None` if no match. `scalar_one_or_none()` differs from `scalar()` (which raises if no match) and `scalars()` (which returns all matches as a list).

```python
    async def upsert_mastery(
        self, user_id: str, concept_id: str, mastery: float
    ) -> AILearnerProfile:
        session = await self._get_session()
        profile = await self.get(user_id)
        if profile is None:
            profile = AILearnerProfile(
                user_id=uuid.UUID(user_id),
                mastery_map={concept_id: {"mastery": mastery}},
            )
            session.add(profile)
        else:
            mm = dict(profile.mastery_map)
            existing = mm.get(concept_id, {})
            if isinstance(existing, dict):
                existing["mastery"] = mastery
            mm[concept_id] = existing
            profile.mastery_map = mm
        await session.commit()
        await session.refresh(profile)
        return profile
```

**Upsert mastery for a concept:**
1. Loads existing profile (or creates new)
2. If profile is None → creates new `AILearnerProfile` with initial mastery map
3. If profile exists → updates the specific concept's mastery in the JSON dict
4. `dict(profile.mastery_map)` — Creates a mutable copy (SQLAlchemy tracks mutations on JSON columns; explicit copy ensures the change is detected)
5. `session.commit()` — Persists changes to DB
6. `session.refresh(profile)` — Re-reads from DB to get server-generated defaults (like `updated_at`)

```python
    async def update_struggle_patterns(
        self, user_id: str, patterns: dict[str, Any]
    ) -> None:
        session = await self._get_session()
        profile = await self.get(user_id)
        if profile is None:
            return
        sp = dict(profile.struggle_patterns)
        sp.update(patterns)
        profile.struggle_patterns = sp
        await session.commit()
```

Merges new struggle patterns into existing ones. Uses `dict.update()` for partial merge rather than full replace.

```python
    async def append_intervention(
        self, user_id: str, intervention: dict[str, Any]
    ) -> None:
        session = await self._get_session()
        profile = await self.get(user_id)
        if profile is None:
            return
        ilog = list(profile.intervention_log)
        ilog.append(intervention)
        if len(ilog) > 100:
            ilog = ilog[-100:]
        profile.intervention_log = ilog
        await session.commit()
```

Appends intervention to the user's history log. **Capped at 100** to prevent unbounded JSON growth. `list(profile.intervention_log)` creates a mutable copy; SQLAlchemy detects the reassignment and updates the column on commit.

---

## Repo 2: `InterventionRepo` (`src/db/repositories/intervention_repo.py`)

### Purpose

Creates and queries `AIInterventionLog` records. Used by ACT (to persist interventions) and effectiveness tracking (to update labels).

### Key Methods

```python
async def create(self, user_id, session_id, cycle_number, diagnosed_concepts,
                 intervention_type, intervention_data, engagement_score,
                 was_exploration, arm_id) -> AIInterventionLog:
```

Creates a new intervention log record with all fields populated from the ACT node's output.

```python
async def update_effectiveness(
    self, intervention_id: str, label: str, score_delta: float
) -> None:
```

Called asynchronously after the next OODA cycle measures impact. Updates the `effectiveness_label` and `score_delta` columns.

```python
async def get_recent(self, user_id: str, limit: int = 5) -> list[AIInterventionLog]:
```

Returns the most recent interventions for a user, ordered by `delivered_at` DESC. Used by the PAUSE node to check cooldown timing.

---

## Repo 3: `WisdomRepo` (`src/db/repositories/wisdom_repo.py`)

### Purpose

Accesses the `AIWisdomStore` table for Thompson Sampling. Used by DECIDE to fetch candidate intervention arm parameters.

### Key Methods

```python
async def get_or_create(
    self, concept_id: str, intervention_type: str,
    profile_segment: dict
) -> AIWisdomStore:
```

**The most important method.** Checks if a wisdom record exists for this (concept, intervention_type, profile_segment) combination. If not, creates one with default α=β=1.0 (uniform Beta distribution). This is a "find or create" pattern — no separate check+insert needed.

```python
async def update_beta(
    self, wisdom_id: str, success: bool
) -> None:
```

Updates Thompson parameters after an intervention outcome is measured:
- If `success=True`: `alpha += 1` (one more success)
- If `success=False`: `beta_param += 1` (one more failure)
- Also updates `total_trials += 1` and recalculates `success_rate`

```python
async def query_by_concept(self, concept_id: str) -> list[AIWisdomStore]:
```

Returns all wisdom records for a concept across all intervention types. Used by DECIDE to compare all candidate arms.

---

## Repo 4: `ConceptRepo` (`src/db/repositories/concept_repo.py`)

### Purpose

Accesses the concept graph (AIConcept, AIConceptEdge, AIConceptMapping). Used by ORIENT for prerequisite analysis and by the concept graph router for API queries.

### Key Methods

```python
async def get(self, concept_id: str) -> AIConcept | None:
async def get_neighbors(
    self, concept_id: str, relation: str = "prerequisite"
) -> list[dict]:
```

Uses a **recursive CTE** (Common Table Expression) to walk the graph:

```sql
WITH RECURSIVE prereq_chain AS (
    SELECT source_id, target_id, 1 AS depth
    FROM ai_concept_edges
    WHERE target_id = :concept_id AND relation = :relation
    UNION ALL
    SELECT e.source_id, e.target_id, pc.depth + 1
    FROM ai_concept_edges e
    JOIN prereq_chain pc ON e.target_id = pc.source_id
)
SELECT * FROM prereq_chain ORDER BY depth;
```

This walks the prerequisite graph up to arbitrary depth — finding all indirect prerequisites of a concept.

```python
async def semantic_search(
    self, query_embedding: list[float], limit: int = 5
) -> list[AIConcept]:
```

**pgvector ANN search.** Executes:

```sql
SELECT * FROM ai_concepts
ORDER BY embedding <=> :query_embedding
LIMIT :limit
```

The `<=>` operator computes cosine distance. With an HNSW index on the embedding column, this returns results in milliseconds even with millions of concepts.

```python
async def get_prerequisite_chain(
    self, concept_id: str
) -> list[AIConcept]:
```

Returns the ordered prerequisite chain using the recursive CTE above.

---

## Repo 5: `BenchmarkRepo` (`src/db/repositories/benchmark_repo.py`)

### Purpose

Simple CRUD for `AIPopulationBenchmark`. Used by ORIENT to compare individual learners against population averages.

### Key Methods

```python
async def get(self, concept_id: str) -> AIPopulationBenchmark | None:
async def upsert(self, concept_id: str, stats: dict) -> AIPopulationBenchmark:
```

## How Repos Connect to the OODA Loop

```
OBSERVE ──→ (no repo calls — pure event aggregation)
ORIENT  ──→ LearnerProfileRepo.get()          → "what does this learner know?"
        ──→ ConceptRepo.get_neighbors()        → "what are the prerequisites?"
        ──→ BenchmarkRepo.get()                → "how does this learner compare?"
DECIDE  ──→ WisdomRepo.get_or_create()         → "what interventions work for this profile?"
ACT     ──→ InterventionRepo.create()          → "record what was delivered"
        ──→ LearnerProfileRepo.append_intervention() → "update learner history"
PAUSE   ──→ (no repo calls — pure time-based logic)
```

## PoC Presentation Idea

Show the "data flow" through repos:

```python
# Simulate an OODA cycle's repo calls
from src.db.repositories.learner_profile_repo import LearnerProfileRepo
from src.db.repositories.wisdom_repo import WisdomRepo

async def demo_repo_flow():
    profile_repo = LearnerProfileRepo()
    wisdom_repo = WisdomRepo()
    
    # ORIENT: load profile
    profile = await profile_repo.get("demo-user")
    print(f"Mastery keys: {list(profile.mastery_map.keys()) if profile else 'no profile'}")
    
    # DECIDE: get wisdom for struggling concepts
    wisdom = await wisdom_repo.get_or_create("ik-inverse-kinematics", "concept_explanation", {"mastery_range": [0, 0.5]})
    print(f"Thompson alpha={wisdom.alpha}, beta={wisdom.beta_param}")
    
    # ACT: append intervention
    await profile_repo.append_intervention("demo-user", {"type": "encouragement", "delivered_at": "..."})
    print("Intervention logged")
```

If PostgreSQL is down, each call raises an exception that the node's try/except catches.
