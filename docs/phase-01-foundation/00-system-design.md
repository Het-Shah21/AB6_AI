# Phase 1 — Foundation: System Design Diagrams

This file is the **visual map** of Phase 1 (Foundation). It shows how the
project skeleton, configuration, persistence layer, and shared utilities fit
together. All other phases build on top of this layer.

---

## 1.1 — Layered View of Phase 1

Phase 1 produces a strict 4-layer cake. Higher layers depend on lower layers
but never the other way around.

```mermaid
flowchart TB
    subgraph L1["Configuration & Environment"]
        ENV[".env / .env.example"]
        SET["src/config/settings.py<br>Settings (BaseSettings)"]
        LCFG["src/config/llm_config.py<br>LLM_CONFIG dict"]
    end

    subgraph L2["Database Engine"]
        ENG["src/db/engine.py<br>AsyncEngine + SessionMaker"]
        BASE["DeclarativeBase"]
    end

    subgraph L3["ORM Models (7 tables)"]
        M1[("ai_learner_profiles")]
        M2[("ai_intervention_logs")]
        M3[("ai_wisdom_store")]
        M4[("ai_concepts")]
        M5[("ai_concept_edges")]
        M6[("ai_concept_mappings")]
        M7[("ai_population_benchmarks")]
    end

    subgraph L4["Repositories (5)"]
        R1["LearnerProfileRepo"]
        R2["InterventionRepo"]
        R3["WisdomRepo"]
        R4["ConceptRepo"]
        R5["BenchmarkRepo"]
    end

    subgraph L5["Shared Utilities"]
        EX["shared/exceptions.py<br>(AB6AIError tree)"]
        EV["shared/events.py<br>(Pydantic event models)"]
        TM["shared/telemetry_math.py<br>(jerk, smoothness, engagement)"]
    end

    ENV --> SET
    LCFG --> SET
    SET --> ENG
    BASE --> ENG
    ENG --> M1 & M2 & M3 & M4 & M5 & M6 & M7
    M1 --> R1
    M2 --> R2
    M3 --> R3
    M4 --> R4
    M5 --> R4
    M6 --> R4
    M7 --> R5
    EX -. "raises" .- R1 & R2 & R3 & R4 & R5
    EV -. "validates" .- R1 & R2
    TM -. "feeds" .- EV
```

---

## 1.2 — Database Schema (Entity-Relationship)

The 7 ORM models in the `ab6_learning_data` PostgreSQL schema. Foreign-key
relationships are solid arrows; JSON-derived references are dashed.

```mermaid
erDiagram
    LEARNER_PROFILE ||--o{ INTERVENTION_LOG : "logs"
    LEARNER_PROFILE {
        uuid id PK
        uuid user_id UK
        jsonb mastery_map
        jsonb learning_style
        jsonb engagement_history
        jsonb intervention_log
        jsonb struggle_patterns
        jsonb prior_baseline
    }
    INTERVENTION_LOG {
        uuid id PK
        uuid user_id FK
        string session_id
        int cycle_number
        jsonb diagnosed_concepts
        string intervention_type
        jsonb intervention_data
        float engagement_score
        bool was_exploration
        string arm_id
        string effectiveness_label
        float score_delta
    }
    WISDOM_STORE {
        uuid id PK
        string concept_id
        string intervention_type
        jsonb profile_segment
        float alpha
        float beta_param
        int total_trials
        float success_rate
    }
    CONCEPT ||--o{ CONCEPT_EDGE : "source / target"
    CONCEPT ||--o{ CONCEPT_MAPPING : "linked to"
    CONCEPT {
        uuid id PK
        string concept_id UK
        string name
        string domain
        float difficulty
        vector embedding
    }
    CONCEPT_EDGE {
        uuid id PK
        string source_id FK
        string target_id FK
        string relation
        float weight
    }
    CONCEPT_MAPPING {
        uuid id PK
        string concept_id FK
        string external_type
        string external_id
        float relevance_score
    }
    POPULATION_BENCHMARK {
        uuid id PK
        string concept_id UK
        float avg_mastery
        float median_mastery
        float p25_mastery
        float p75_mastery
        int avg_attempts
        jsonb common_gaps
    }
    INTERVENTION_LOG ||--o{ WISDOM_STORE : "feedback updates alpha/beta"
    LEARNER_PROFILE ||--o{ POPULATION_BENCHMARK : "compared against"
```

---

## 1.3 — Configuration Resolution Chain

How a `get_settings()` call flows from `.env` to typed Python object.

```mermaid
flowchart LR
    A[".env file<br>(gitignored)"] -->|overrides| D
    B["Environment Variables<br>(shell)"] -->|highest priority| D
    C["Defaults in<br>Settings class"] -->|lowest priority| D
    D["pydantic-settings<br>BaseSettings.__init__"] --> E["Validated Settings<br>singleton (lru_cache)"]
    E --> F1["engine.database_url"]
    E --> F2["provider.openai_api_key"]
    E --> F3["settings.llm_rate_limit_rpm"]
    E --> F4["settings.redis_stream_*"]
```

---

## 1.4 — Database Engine Boot Sequence

Lazy initialization pattern used everywhere in the project. The engine and
session-factory are only created on first use, then cached for the process
lifetime.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Engine as engine.py
    participant Settings
    participant SA as SQLAlchemy
    participant PG as PostgreSQL

    Caller->>Engine: get_engine()
    alt _engine is None
        Engine->>Settings: get_settings()
        Settings-->>Engine: database_url
        Engine->>SA: create_async_engine(url, pool=10, overflow=20)
        SA-->>Engine: AsyncEngine
    end
    Engine-->>Caller: cached AsyncEngine

    Caller->>Engine: get_session()
    Engine->>Engine: get_session_factory()
    Engine->>SA: async_sessionmaker(engine, expire_on_commit=False)
    SA-->>Engine: SessionMaker
    Engine-->>Caller: AsyncSession

    Caller->>SA: session.execute(...)
    SA->>PG: SQL over asyncpg
    PG-->>SA: rows
    SA-->>Caller: result
```

---

## 1.5 — Repository Pattern (How Nodes Reach Data)

Repositories are the **only** path from agent nodes to the database. They
encapsulate SQL and let the rest of the code deal in Python objects.

```mermaid
flowchart LR
    N["OODA Node<br>(Phase 5)"] -->|uses| REPO
    subgraph REPO["Repository Layer (5)"]
        direction TB
        LP[LearnerProfileRepo]
        IR[InterventionRepo]
        WR[WisdomRepo]
        CR[ConceptRepo]
        BR[BenchmarkRepo]
    end
    REPO -->|session.execute| ENG[("AsyncEngine<br>+ SessionMaker")]
    ENG --> PG[(PostgreSQL 18 + pgvector)]
    REPO -->|domain objects| N

    style REPO fill:#fef3c7,stroke:#b45309
    style PG fill:#dbeafe,stroke:#1d4ed8
```

---

## 1.6 — Exception Hierarchy

```mermaid
classDiagram
    class Exception
    class AB6AIError
    class LLMError
    class LLMFallbackExhaustedError
    class SanitizationError
    class ConceptGraphError
    class InterventionError
    class AgentError
    class MemoryError
    class IngestionError
    class ChallengeGenerationError

    Exception <|-- AB6AIError
    AB6AIError <|-- LLMError
    LLMError <|-- LLMFallbackExhaustedError
    AB6AIError <|-- SanitizationError
    AB6AIError <|-- ConceptGraphError
    AB6AIError <|-- InterventionError
    AB6AIError <|-- AgentError
    AB6AIError <|-- MemoryError
    AB6AIError <|-- IngestionError
    AB6AIError <|-- ChallengeGenerationError
```

---

## 1.7 — Container View (docker-compose)

```mermaid
flowchart LR
    subgraph DC["docker-compose.yml"]
        API["api service<br>uvicorn src.api.app:app"]
        PG[("postgres<br>pgvector/pgvector:pg18")]
        RD[("redis<br>redis:7-alpine")]
    end
    API -->|asyncpg| PG
    API -->|aioredis| RD
    API -->|python -m arq| RD
```

---

## 1.8 — What Phase 1 Delivers vs. What It Does Not

```mermaid
mindmap
  Phase 1 Foundation
    In scope
      pyproject.toml
      settings + llm_config
      Async engine + session factory
      7 ORM models
      5 repositories
      shared exceptions/events/math
      alembic migrations
      docker compose
    Out of scope (later phases)
      LLM provider fallback
      Redis stream consumer
      Concept extraction builder
      OODA state machine
      Memory services
      API routers
      Tests + demos
```

---

## 1.9 — Reading Order for Phase 1

```mermaid
flowchart LR
    01[01 pyproject.toml] --> 02[02 .env / .gitignore]
    02 --> 03[03 settings.py]
    03 --> 04[04 llm_config.py]
    03 --> 05[05 engine.py]
    05 --> 06[06 ORM models]
    06 --> 07[07 repositories]
    03 --> 08[08 shared utilities]
```

Read in this order; each file depends on the previous one.
