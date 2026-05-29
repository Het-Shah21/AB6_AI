# Task 1.6 — ORM Models: All 7 Tables

## System Design Reference

Master System Design, "Data Layer — Schema Design" section. The schema specified 7 tables in the `ab6_learning_data` schema: learner profiles, intervention logs, wisdom store, concepts, concept edges, concept mappings, and population benchmarks. Each table maps to one logical domain in the architecture.

---

## Model 1: `AILearnerProfile` (`src/db/models/ai_learner_profile.py`)

### Purpose

Stores per-user state that the OODA loop reads and writes every cycle. This is the **learner's memory** — what they know, how they learn, what they've struggled with, what interventions they've received.

### Line-by-Line

```python
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped

from src.db.engine import Base
```

- `uuid` — Python's built-in UUID generator. PostgreSQL's `UUID` type maps to Python `uuid.UUID` objects.
- `datetime` — For timestamp columns (`created_at`, `updated_at`).
- `Column, String, DateTime, JSON, ForeignKey, Text` — SQLAlchemy column types. `JSON` maps to PostgreSQL's `JSONB` (binary JSON, indexable).
- `UUID` from `sqlalchemy.dialects.postgresql` — PostgreSQL-specific UUID type. Using the generic `sqlalchemy.types.Uuid` wouldn't give us PostgreSQL's native UUID performance.
- `Mapped` — SQLAlchemy 2.0 type annotation marker for ORM-mapped attributes.
- `Base` — The declarative base from `engine.py`. All models inherit from it.

```python
class AILearnerProfile(Base):
    __tablename__ = "ai_learner_profiles"
    __table_args__ = {"schema": "ab6_learning_data"}
```

- `__tablename__` — The actual table name in PostgreSQL (snake_case convention).
- `__table_args__ = {"schema": "ab6_learning_data"}` — Places the table in the `ab6_learning_data` schema instead of the default `public` schema. This organizes AB6-specific tables separately from platform tables.

```python
    id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
```

- `id` — Primary key, UUID type. `as_uuid=True` makes SQLAlchemy return Python `uuid.UUID` objects instead of strings.
- `default=uuid.uuid4` — Auto-generates a random UUID when a new record is created (not on UPDATE).

```python
    user_id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True),
        ForeignKey("ab6_user_data.user_details.id"),
        unique=True,
        nullable=False,
    )
```

- `user_id` — Foreign key to an external `user_details` table in a different schema (`ab6_user_data`). This keeps AB6 data separate from user account data.
- `unique=True` — One profile per user. If a user already has a profile, upsert instead of insert.
- `nullable=False` — Every profile must reference a user.

```python
    mastery_map = Column(JSON, nullable=False, default=dict)
```

- `mastery_map` — JSON dict mapping concept_id → mastery data. Example: `{"ik-inverse-kinematics": {"mastery": 0.3, "last_attempt": "2026-05-29T...", "attempts": 5}}`
- `default=dict` — New profiles start with an empty dict rather than NULL. This simplifies code: no need to check for None before calling `.get()`.

```python
    learning_style = Column(JSON, nullable=False, default=dict)
```

- `learning_style` — Learner's preferred modality. Example: `{"prefers": "visual", "code_over_text": 0.7, "video_engagement": 0.8}`
- Defaults to empty dict. Filled in by the ORIENT node over time.

```python
    engagement_history = Column(JSON, nullable=False, default=list)
```

- `engagement_history` — Ordered list of engagement scores over time. Example: `[{"score": 0.5, "timestamp": "..."}, {"score": 0.6, "timestamp": "..."}]`
- Used by ORIENT to compute engagement trend (improving/declining/stable).

```python
    intervention_log = Column(JSON, nullable=False, default=list)
```

- `intervention_log` — List of past interventions delivered to this user. Each entry contains the full intervention payload. Capped at 100 entries in the repository.

```python
    struggle_patterns = Column(JSON, nullable=False, default=dict)
```

- `struggle_patterns` — Diagnosed struggle patterns. Example: `{"ik-inverse-kinematics": {"count": 3, "first_seen": "...", "symptoms": ["high_error_rate", "code_iterations"]}}`

```python
    prior_baseline = Column(JSON, nullable=False, default=dict)
```

- `prior_baseline` — Initial assessment data. Captured when the student first starts, used by ORIENT to measure progress. Example: `{"pretest_score": 0.4, "self_assessed_confidence": {"ik": 2}}`

```python
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
```

- `created_at` — Set once on INSERT. `DateTime(timezone=True)` stores timestamps with timezone info.
- `updated_at` — Updated on every INSERT and UPDATE via `onupdate=datetime.utcnow`. SQLAlchemy automatically calls `onupdate` for each UPDATE.

---

## Model 2: `AIInterventionLog` (`src/db/models/ai_intervention_log.py`)

### Purpose

Records every intervention delivered by the ACT node. Used by the effectiveness tracker (Phase 7) to score outcomes and update the wisdom store.

### Line-by-Line

```python
class AIInterventionLog(Base):
    __tablename__ = "ai_intervention_logs"
    __table_args__ = {"schema": "ab6_learning_data"}
```

Same schema as the profile model.

```python
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("ab6_user_data.user_details.id"), nullable=False)
    session_id = Column(String(100), nullable=False)
    cycle_number = Column(Integer, nullable=False)
```

- `id` — Unique intervention ID (UUID).
- `user_id` — Recipient of the intervention.
- `session_id` — Session during which the intervention was delivered.
- `cycle_number` — Which OODA cycle number this was delivered on. Used for ordering and analysis.

```python
    diagnosed_concepts = Column(JSON, nullable=False, default=list)
    intervention_type = Column(String(50), nullable=False)
    intervention_data = Column(JSON, nullable=False)
    engagement_score = Column(Float, nullable=False, default=0.5)
    was_exploration = Column(Boolean, nullable=False, default=False)
    arm_id = Column(String(200), nullable=True)
```

- `diagnosed_concepts` — List of concept IDs the ORIENT node identified as struggles.
- `intervention_type` — One of 7 types: `concept_explanation`, `video_recommendation`, `prerequisite_nudge`, `challenge_hint`, `challenge_swap`, `revision_prompt`, `encouragement`.
- `intervention_data` — Full JSON payload delivered to the user (title, body, display metadata).
- `engagement_score` — Engagement score at the time of delivery. Used to measure if engagement changed after intervention.
- `was_exploration` — Whether this was an exploration trial (Thompson sample with <10 trials).
- `arm_id` — Multi-armed bandit arm identifier: `"{concept_id}:{intervention_type}"`. Used for statistical analysis.

```python
    effectiveness_label = Column(String(20), nullable=True)
    score_delta = Column(Float, nullable=True)
    delivered_at = Column(DateTime(timezone=True), default=datetime.utcnow)
```

- `effectiveness_label` — Set later by `measure_effectiveness()`: `"positive"`, `"negative"`, or `"neutral"`.
- `score_delta` — Pre/post intervention score change.
- `delivered_at` — When the intervention was sent.

---

## Model 3: `AIWisdomStore` (`src/db/models/ai_wisdom_store.py`)

### Purpose

Stores Thompson Sampling parameters (alpha, beta) for every (concept, intervention_type, profile_segment) combination. This is the **global wisdom** — what interventions work best for which students on which concepts.

### Line-by-Line

```python
class AIWisdomStore(Base):
    __tablename__ = "ai_wisdom_store"
    __table_args__ = {"schema": "ab6_learning_data"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concept_id = Column(String(100), nullable=False)
    intervention_type = Column(String(50), nullable=False)
    profile_segment = Column(JSON, nullable=False, default=dict)
```

- `concept_id` — The concept this wisdom applies to.
- `intervention_type` — The type of intervention.
- `profile_segment` — JSON describing which learner segment this applies to. Example: `{"mastery_range": [0.3, 0.7], "learning_style": "visual", "struggle_count_gte": 3}`. Allows targeting wisdom to specific learner profiles.

```python
    alpha = Column(Float, nullable=False, default=1.0)
    beta_param = Column(Float, nullable=False, default=1.0)
```

**Thompson Sampling parameters:**
- `alpha` — Number of successful trials + 1. Starts at 1.0 (uniform prior).
- `beta_param` — Number of failed trials + 1. Starts at 1.0 (uniform prior).

Together they define a Beta distribution: `Beta(alpha, beta)`. The Thompson sample is drawn from `np.random.beta(alpha, beta)`. Higher alpha means more successes → higher sample → more likely to be selected.

```python
    total_trials = Column(Integer, nullable=False, default=0)
    success_rate = Column(Float, nullable=False, default=0.5)
```

- `total_trials` — Number of times this arm was tried.
- `success_rate` — `alpha / (alpha + beta)`. Cached for quick queries.

```python
    insight_text = Column(Text, nullable=True)
```

Free-text field for LLM-generated insights about why this intervention works. Example: `"Visual explanations with annotated diagrams improve mastery of inverse kinematics for students in the 0.3-0.7 mastery range."`

```python
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
```

---

## Model 4: `AIConcept` (`src/db/models/ai_concept.py`)

### Purpose

Represents a single concept in the concept graph. Each concept has a name, description, domain, difficulty level, and a **pgvector embedding** for semantic search.

### Line-by-Line

```python
from pgvector.sqlalchemy import Vector
```

**Critical import.** `Vector` is not a standard SQLAlchemy type — it comes from the `pgvector` package. It maps to PostgreSQL's `vector(1536)` type, where 1536 is the dimensionality of OpenAI's `text-embedding-3-small` model.

```python
class AIConcept(Base):
    __tablename__ = "ai_concepts"
    __table_args__ = {"schema": "ab6_learning_data"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concept_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    domain = Column(String(100), nullable=True)
    difficulty = Column(Float, nullable=True, default=0.5)
```

- `concept_id` — Human-readable unique ID like `"ik-inverse-kinematics"`.
- `difficulty` — 0.0 (easiest) to 1.0 (hardest). Can be set manually or inferred from prerequisite depth.

```python
    embedding = Column(Vector(1536), nullable=True)
```

**The pgvector column.** `Vector(1536)` creates a PostgreSQL column of type `vector(1536)`. This enables:
- `SELECT * FROM ai_concepts ORDER BY embedding <=> '[0.1, 0.2, ...]' LIMIT 5` — cosine distance search
- `CREATE INDEX ON ai_concepts USING hnsw (embedding vector_cosine_ops)` — HNSW index for fast approximate search

```python
    source = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
```

- `source` — Where this concept came from: `"llm_extracted"`, `"manual"`, `"curriculum_import"`.

---

## Model 5: `AIConceptEdge` (`src/db/models/ai_concept_edge.py`)

### Purpose

Directed edges in the concept graph. Each edge connects two concepts with a relation type and weight.

```python
class AIConceptEdge(Base):
    __tablename__ = "ai_concept_edges"
    __table_args__ = {"schema": "ab6_learning_data"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(String(100), ForeignKey("ab6_learning_data.ai_concepts.concept_id"), nullable=False)
    target_id = Column(String(100), ForeignKey("ab6_learning_data.ai_concepts.concept_id"), nullable=False)
    relation = Column(String(50), nullable=False, default="prerequisite")
    weight = Column(Float, nullable=False, default=1.0)
    source = Column(String(50), nullable=True)
```

- `source_id → target_id`: If `relation="prerequisite"`, then `source_id` is a prerequisite of `target_id`.
- `relation`: `"prerequisite"` (must know A before B) or `"dependency"` (B builds on A but not strictly required).
- `weight`: Importance of the edge. Higher weight = stronger prerequisite relationship.

---

## Model 6: `AIConceptMapping` (`src/db/models/ai_concept_mapping.py`)

### Purpose

Links concepts to external entities (videos, challenges, readings). This is how the agent knows "the video on inverse kinematics teaches concept X" or "challenge 5 tests concept Y".

```python
class AIConceptMapping(Base):
    __tablename__ = "ai_concept_mappings"
    __table_args__ = {"schema": "ab6_learning_data"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concept_id = Column(String(100), ForeignKey("ab6_learning_data.ai_concepts.concept_id"), nullable=False)
    external_type = Column(String(50), nullable=False)
    external_id = Column(String(255), nullable=False)
    relevance_score = Column(Float, nullable=False, default=0.5)
```

- `external_type`: `"video"`, `"challenge"`, `"reading"`, `"quiz"`.
- `relevance_score`: How well this external entity teaches the concept (0.0 to 1.0).

---

## Model 7: `AIPopulationBenchmark` (`src/db/models/ai_population_benchmark.py`)

### Purpose

Per-concept aggregate statistics across all learners. Used by ORIENT to compare an individual learner against the population.

```python
class AIPopulationBenchmark(Base):
    __tablename__ = "ai_population_benchmarks"
    __table_args__ = {"schema": "ab6_learning_data"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concept_id = Column(String(100), unique=True, nullable=False)
    avg_mastery = Column(Float, nullable=False, default=0.0)
    median_mastery = Column(Float, nullable=False, default=0.0)
    p25_mastery = Column(Float, nullable=False, default=0.0)
    p75_mastery = Column(Float, nullable=False, default=0.0)
    avg_attempts = Column(Integer, nullable=False, default=0)
    avg_time_on_task = Column(Float, nullable=False, default=0.0)
    common_gaps = Column(JSON, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
```

- `avg_mastery`, `median_mastery`, `p25_mastery`, `p75_mastery` — Distribution of mastery scores across all learners. If a learner's mastery is below p25, they're struggling more than 75% of peers.
- `common_gaps` — JSON list of prerequisite concepts that learners commonly struggle with. Example: `["basic-trigonometry", "coordinate-systems"]`.

## How They Connect

```
                     ┌──────────────────┐
                     │ AILearnerProfile │── one per user, updated every OODA cycle
                     └────────┬─────────┘
                              │ logs interventions
                              ▼
┌──────────────────────────────────────────────────┐
│              AIInterventionLog                    │── one per intervention delivered
└──────────────────────┬───────────────────────────┘
                       │ feeds effectiveness data
                       ▼
┌──────────────────────────────────────────────────┐
│                AIWisdomStore                      │── Thompson params per concept+type+segment
└──────────────────────────────────────────────────┘

┌────────────┐     ┌──────────────┐     ┌──────────────────┐
│ AIConcept  │────→│AIConceptEdge │     │AIConceptMapping  │──→ videos, challenges
│(nodes)     │     │(edges)       │     │(external links)  │
└────────────┘     └──────────────┘     └──────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────┐
│         AIPopulationBenchmark                     │── per-concept population stats
└──────────────────────────────────────────────────┘
```

## PoC Presentation Idea

Print the ER diagram on a large poster with color codes:
- **Blue** — User data (profiles, intervention logs)
- **Orange** — Wisdom (Thompson sampling store)
- **Green** — Knowledge (concepts, edges, mappings)
- **Red** — Analytics (population benchmarks)

Show SQL queries:

```sql
-- Find all prerequisites for a concept the learner is struggling with
SELECT c.* FROM ai_concept_edges e
JOIN ai_concepts c ON c.concept_id = e.target_id
WHERE e.source_id = 'ik-inverse-kinematics' AND e.relation = 'prerequisite';

-- Get Thompson sample for an intervention arm
SELECT alpha / (alpha + beta_param) as success_rate
FROM ai_wisdom_store
WHERE concept_id = 'ik-inverse-kinematics'
  AND intervention_type = 'concept_explanation';
```
