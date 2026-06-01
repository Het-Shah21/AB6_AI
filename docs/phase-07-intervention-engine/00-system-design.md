# Phase 7 — Intervention Engine: System Design Diagrams

The Intervention Engine is the **decision → content → delivery** pipeline that
turns the DECIDE node's chosen arm into a personalized message streamed to
the student's browser.

---

## 7.1 — High-Level Pipeline

```mermaid
flowchart LR
    A["DECIDE node<br>(Thompson sample)"] --> B["InterventionSelector<br>(selector.py)"]
    B --> C["candidate[] with<br>alpha / beta_param"]
    C --> D["Thompson sample<br>argmax"]
    D --> E["selected_intervention"]
    E --> F["Delivery.prepare_and_deliver()"]
    F --> G["InterventionGenerator<br>(LLM)"]
    G --> H["personalized content"]
    H --> I{"channel"}
    I -- websocket --> J["WebSocket push"]
    I -- sse --> K["SSE stream"]
    I -- none --> L["logged only<br>(exploration)"]
    J --> M["InterventionRepo.create()"]
    K --> M
    L --> M
    M --> N["next cycle:<br>measure_effectiveness()<br>updates alpha/beta"]
    N --> B
```

---

## 7.2 — Selector Detail (Phase 7 §7.1)

The selector returns **candidate arms** ordered by expected effectiveness.
The DECIDE node then samples one with Thompson.

```mermaid
flowchart TB
    IN["(struggles[], profile, engagement)"] --> S1["1. Type matching by learning_style"]
    S1 --> S2["2. Difficulty calibration by engagement + mastery"]
    S2 --> S3["3. Community boost (GlobalWisdom.success_rate)"]
    S3 --> S4["4. History dedup<br>(last 5 same type+concept excluded)"]
    S4 --> OUT["candidates[]<br>(each: type, concept, rationale,<br>success_count, trial_count, expected_effectiveness)"]
```

The four heuristics in detail:

| Step | Rule | Source |
|---|---|---|
| Type matching | visual/reading → video_recommendation; hands-on → hint + practice; reflective → code_review | profile.learning_style |
| Difficulty | engagement < 0.3 → encouragement; 0.3–0.6 → hint; 0.6–0.8 → practice; > 0.8 → code_review | profile + telemetry |
| Community boost | 1.5× weight on expected_effectiveness if GlobalWisdom reports high success | ai_wisdom_store |
| History dedup | exclude if same type+concept was used in the last 5 interventions | profile.intervention_log |

---

## 7.3 — Thompson Sampling Convergence

```mermaid
flowchart LR
    subgraph T1["Trial 1 — all arms have Beta(1,1)"]
        A1["hint: 0.72"]:::arm
        B1["practice: 0.31"]:::arm
        C1["video: 0.55"]:::arm
    end
    subgraph T5["Trial 5 — posteriors start to separate"]
        A5["hint Beta(3,2) → 0.68"]:::arm
        B5["practice Beta(2,2) → 0.45"]:::arm
        C5["video Beta(1,4) → 0.12"]:::arm
    end
    subgraph T10["Trial 10 — clear winner"]
        A10["hint Beta(6,4) → 0.61"]:::arm
        B10["practice Beta(4,2) → 0.73"]:::arm
        C10["video Beta(1,9) → 0.08"]:::arm
    end
    T1 --> T5 --> T10

    classDef arm fill:#dbeafe,stroke:#1d4ed8
```

Initially uniform priors. After 10 trials, the agent has **discovered** that
practice is the best arm for this concept — even though `hint` was the first
choice. Thompson sampling automatically transitions from explore to exploit.

---

## 7.4 — Generator Pipeline (LLM-driven)

```mermaid
flowchart TB
    IN["(type, concept, profile, struggles, extra_context)"] --> F["format ACT_PROMPT_TEMPLATE"]
    F --> LLM["get_llm_for_purpose('reasoning')"]
    LLM --> R["response.content"]
    R --> OUT["{type, concept_id, content, timestamp}"]
    OUT --> DEL["DeliveryManager"]
```

The generator is **stateless** — every call re-formats the prompt from
current state. This makes it trivially cacheable and replayable.

---

## 7.5 — Challenge Generation Sub-flow (Generator Detail)

```mermaid
flowchart TB
    A["generate_challenge(concept_id, difficulty, type)"] --> B["ConceptRepo.get_with_neighbors()"]
    B --> C["format CHALLENGE_GENERATION_PROMPT"]
    C --> D["llm.ainvoke() → draft challenge"]
    D --> E["parse JSON"]
    E --> F["CRITIQUE_PROMPT → llm.ainvoke()"]
    F --> G{"quality_score >= 0.7?"}
    G -- No --> H["_regenerate_with_feedback()<br>(one retry with critique)"]
    G -- Yes --> I["calibrate_difficulty(challenge, concept)"]
    H --> I
    I --> J["{concept_id, difficulty, quality_score, ...}"]
```

The challenge generator uses **two LLM calls**: one to produce, one to
critique, and a regeneration loop if quality is below 0.7.

---

## 7.6 — Delivery Channels

```mermaid
flowchart LR
    P["intervention payload"] --> C{"delivery_channel"}
    C -- websocket --> WS["WebSocket<br>(_active_connections[user_id])"]
    C -- sse --> SSE["SSE generator<br>(sse_starlette)"]
    C -- none --> NONE["only logged<br>(safe exploration)"]
    WS --> STU["Student browser"]
    SSE --> STU
    NONE --> LOG["ai_intervention_logs"]
```

> WebSocket registration is per-user; a user may have **multiple browser
> tabs** open and each gets the message.

---

## 7.7 — Effectiveness Feedback Loop (Cross-Phase)

This loop closes Phase 6 ↔ Phase 7 ↔ Phase 5.

```mermaid
sequenceDiagram
    autonumber
    participant D as DECIDE
    participant S as Selector
    participant W as WisdomRepo
    participant A as ACT
    participant DEL as Delivery (WS/SSE)
    participant STU as Student
    participant E as EffectivenessTracker
    participant DB

    D->>S: select(struggles, profile, engagement)
    S->>W: get_or_create(concept_id, type, segment)
    W-->>S: {alpha, beta_param, total_trials}
    S-->>D: candidates[]
    D-->>D: Thompson sample → selected
    D->>A: selected_intervention
    A->>A: generate content (LLM)
    A->>DEL: deliver_via_websocket(user_id, payload)
    DEL->>STU: ws.send_json(payload)
    Note over STU: Time passes — student tries next challenge
    E->>DB: score_after - score_before
    E->>W: update_beta(wisdom_id, success)
    W-->>W: alpha++ or beta_param++
```

---

## 7.8 — Intervention Types

The 7 supported intervention types and what they map to.

| Type | Generator | Default channel | When used |
|---|---|---|---|
| `concept_explanation` | `generate_concept_explanation()` | websocket | mastery 0.3–0.6 + new concept |
| `video_recommendation` | `find_best_video_for_concept()` | websocket | visual learner + low engagement |
| `prerequisite_nudge` | LLM | websocket | unmastered prerequisite detected |
| `challenge_hint` | LLM | websocket | struggle on active challenge |
| `challenge_swap` | `generate_challenge()` | websocket | mastery > 0.6 (try harder) |
| `revision_prompt` | LLM | websocket | long gap since last activity |
| `encouragement` | LLM | websocket | engagement < 0.3 |

---

## 7.9 — Phase 7 Component Map

```mermaid
flowchart LR
    subgraph P7["src/intervention/"]
        SE["selector.py<br>(select_intervention, segment_learner, find_best_video_for_concept)"]
        G["generator.py<br>(generate_challenge, generate_concept_explanation)"]
        E["effectiveness.py<br>(measure_effectiveness, calibrate_difficulty)"]
        D["delivery.py<br>(WebSocket + SSE channels)"]
    end
    subgraph DEPS["Dependencies"]
        WR["WisdomRepo"]
        BR["BenchmarkRepo"]
        CR["ConceptRepo"]
        IR["InterventionRepo"]
        LPR["LearnerProfileRepo"]
        LLM["llm provider (reasoning / primary)"]
    end
    SE --> WR & BR & CR
    G --> CR & LLM
    E --> IR & LPR
    D --> WS["WebSocket manager"]
    D --> SSE["SSE generator"]
```
