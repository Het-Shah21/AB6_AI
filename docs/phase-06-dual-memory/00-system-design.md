# Phase 6 — Dual Memory: System Design Diagrams

Phase 6 implements the **memory hierarchy** of the agent: short-term (in
process), session (Redis 30 min TTL), long-term profile (PostgreSQL), and
global wisdom (cross-user Thompson parameters).

---

## 6.1 — Memory Layers

```mermaid
flowchart TB
    subgraph L0["L0 — Per-request (in process)"]
        IC["in-memory dicts<br/>(TelemetryAggregator buffers)"]
    end
    subgraph L1["L1 — Session (Redis, TTL 30 min)"]
        SC["SessionCache<br/>session:{id} → state dict"]
    end
    subgraph L2["L2 — Personal (PostgreSQL, persistent)"]
        LP[("ai_learner_profiles<br/>(mastery_map, learning_style,<br/>engagement_history, struggle_patterns)")]
    end
    subgraph L3["L3 — Global (PostgreSQL, cross-user)"]
        WS[("ai_wisdom_store<br/>(alpha, beta per concept+type+segment)")]
        PB[("ai_population_benchmarks<br/>(avg, p25, p75, common_gaps)")]
    end

    IC -->|"obs_window"| OODA["OODA Agent"]
    SC -->|"state restore"| OODA
    LP -->|"profile"| OODA
    WS -->|"Thompson arms"| DECIDE["DECIDE node"]
    PB -->|"peer comparison"| ORIENT["ORIENT node"]
```

Latency hierarchy: L0 < 1 µs · L1 ~1 ms · L2 ~5–15 ms · L3 ~50 ms/concept.

---

## 6.2 — Personal Memory Service

```mermaid
flowchart LR
    subgraph PMS["PersonalMemoryService (src/memory/personal.py)"]
        PM1["get_profile(user_id)"]
        PM2["update_mastery(user_id, concept_id, mastery)"]
        PM3["record_struggle(user_id, concept_id, error_pattern)"]
        PM4["get_intervention_history(user_id, limit)"]
        PM5["update_engagement(user_id, score, context)"]
    end
    PM1 --> LPR["LearnerProfileRepo"]
    PM2 --> LPR
    PM3 --> LPR
    PM4 --> IR["InterventionRepo"]
    PM5 --> LPR
    LPR --> DB1[("ai_learner_profiles")]
    IR --> DB2[("ai_intervention_logs")]
```

---

## 6.3 — Global Wisdom Service

```mermaid
flowchart LR
    subgraph GWS["GlobalWisdomService (src/memory/global_wisdom.py)"]
        G1["get_intervention_stats(concept_id, type, segment)"]
        G2["record_outcome(concept_id, type, segment, success)"]
        G3["get_best_intervention(concept_id, segment)"]
    end
    G1 --> WR["WisdomRepo"]
    G2 --> WR
    G3 --> WR
    WR --> DB[("ai_wisdom_store<br/>(alpha, beta_param, total_trials, success_rate, insight_text)")]
    G2 -- "update_beta: alpha++ or beta++" --> DB
```

The `get_best_intervention` method only returns an arm if it has at least
3 trials and the highest observed success rate — a guard against premature
conclusions from a single noisy trial.

---

## 6.4 — Session Cache Implementations (Swappable)

```mermaid
flowchart TB
    A["SessionCache (Redis)"] -->|set_state| RD["Redis<br/>session:{id}<br/>TTL 1800s"]
    B["InMemorySessionCache (fallback)"] -->|set| MEM["dict[str, dict]"]
    SC["SessionCache (interface)"] -.-> A
    SC -.-> B
    DEC["Dependency injection<br/>based on settings.redis_url"] --> SC
```

Both implementations expose the same async API (`get`, `set`, `delete`,
`get_active_sessions`) so the rest of the code never needs to branch on which
backend is live.

---

## 6.5 — Thompson Sampling Update Loop

```mermaid
sequenceDiagram
    autonumber
    participant ACT as ACT node
    participant STU as Student
    participant INT as InterventionRepo
    participant PMS as PersonalMemoryService
    participant EFF as measure_effectiveness()
    participant GWS as GlobalWisdomService
    participant WR as WisdomRepo
    participant DEC as DECIDE (next cycle)

    ACT->>STU: deliver intervention (websocket)
    STU->>ACT: feedback (next challenge score)
    EFF->>INT: update_effectiveness(id, label, delta)
    EFF->>PMS: update_struggle_patterns(user_id, {effectiveness_*})
    EFF->>GWS: record_outcome(concept_id, type, segment, success)
    GWS->>WR: update_beta(wisdom_id, success)
    WR->>WR: if success: alpha += 1<br/>else: beta_param += 1
    DEC->>WR: get_or_create(concept_id, type, segment)  (next cycle)
    WR-->>DEC: {alpha, beta_param} (now updated)
```

The cycle closes the feedback loop: today's `act` updates the `alpha`/`beta`
that tomorrow's `decide` will sample from.

---

## 6.6 — Population Benchmark vs. Individual Profile

```mermaid
flowchart LR
    A["learner mastery_map[concept_id] = 0.42"] --> C{"vs population"}
    B["ai_population_benchmarks<br/>p25 = 0.55, p75 = 0.85"] --> C
    C -->|"0.42 < p25"| Z["struggling: below 75% of peers"]
    C -->|"p25 <= x <= p75"| N["normal range"]
    C -->|"x > p75"| G["ahead of peers"]
```

The ORIENT node uses this comparison to weight engagement trends and decide
whether to escalate or de-escalate interventions.

---

## 6.7 — Population Benchmark Refresh

```mermaid
flowchart TB
    A["Cron / scheduled job"] --> B["aggregate()"]
    B --> C["for each concept:"]
    C --> D["pull all profiles with concept in mastery_map"]
    D --> E{"peer_count >= 3?"}
    E -- No --> SKIP["skip (insufficient data)"]
    E -- Yes --> F["compute avg / median / p25 / p75<br/>+ common_gaps"]
    F --> G["UPSERT into ai_population_benchmarks"]
```

Privacy invariant: only **aggregated statistics** flow into the global store.
Individual learner rows are never joined with PII.

---

## 6.8 — Phase 6 Component Map

```mermaid
flowchart LR
    subgraph P6["src/memory/"]
        P["personal.py<br/>(PersonalMemoryService)"]
        G["global_wisdom.py<br/>(GlobalWisdomService)"]
        S["session_cache.py<br/>(SessionCache / InMemorySessionCache)"]
        B["population_benchmarks.py<br/>(aggregator)"]
    end
    subgraph DB["db/repositories/"]
        LPR["LearnerProfileRepo"]
        IR["InterventionRepo"]
        WR["WisdomRepo"]
        BR["BenchmarkRepo"]
    end
    P --> LPR & IR
    G --> WR
    S --> RD["Redis"]
    B --> BR
    B --> LPR
    B --> CR["ConceptRepo"]
```
