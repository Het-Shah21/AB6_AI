# Phase 5 — OODA Agent Core: System Design Diagrams

The OODA (Observe → Orient → Decide → Act) state machine is the **heart** of
the AB6 AI agent. Phase 5 wires together state, graph, nodes, tools, and
prompts into a single LangGraph `StateGraph` that runs in a continuous loop.

---

## 5.1 — Full OODA Loop (Authoritative)

This is the exact topology from `src/agent/graph.py`:

```mermaid
flowchart TB
    START([START]) --> OBS

    OBS["observe<br>(observe_node)"] --> CR{"continue_router<br>cycle_count >= max_cycles?"}

    CR -- "yes" --> ENDNODE([END])
    CR -- "no" --> ORI

    ORI["orient<br>(orient_node)"] --> DEC

    DEC["decide<br>(decide_node)"] --> DR{"decide_router<br>should_pause?"}

    DR -- "no" --> ACT
    DR -- "yes" --> PAU

    ACT["act<br>(act_node)"] --> OBS
    PAU["pause<br>(pause_node)"] --> OBS

    classDef oodanode fill:#dbeafe,stroke:#1d4ed8
    classDef oodarouter fill:#fef3c7,stroke:#b45309
    class OBS,ORI,DEC,ACT,PAU oodanode
    class CR,DR oodarouter
```

Key invariants from the code:
- `START → observe` is the only entry.
- `observe → {orient | END}` is the **only** terminal edge.
- `orient → decide` is unconditional.
- `decide → {act | pause}` is the cooldown fork.
- `act → observe` and `pause → observe` close the cycle.

---

## 5.2 — State Lifecycle Through One Cycle

```mermaid
sequenceDiagram
    autonumber
    participant API
    participant Cache as SessionCache (Redis)
    participant Agent as LangGraph Agent
    participant O as observe
    participant Or as orient
    participant D as decide
    participant A as act
    participant DB

    API->>Cache: get_state(user_id)
    Cache-->>API: state (or None)
    API->>Agent: agent.ainvoke(state)
    Agent->>O: invoke(state)
    O-->>Agent: {telemetry_window, observation_summary, raw_events:[]}
    Agent->>Or: invoke(state)
    Or->>DB: LearnerProfileRepo.get()
    Or->>DB: ConceptRepo.get_neighbors() / find_unmastered_prerequisites()
    Or-->>Agent: {diagnosed_struggles, engagement_score, learner_profile}
    Agent->>D: invoke(state)
    D->>DB: WisdomRepo.get_or_create() for each candidate
    D-->>Agent: {selected_intervention, exploration_flag}
    Agent->>A: invoke(state)
    A->>DB: InterventionRepo.create()
    A-->>Agent: {intervention_delivered, cycle_count+1, last_cycle_timestamp}
    Agent-->>API: result
    API->>Cache: set_state(user_id, result)
```

---

## 5.3 — OODAState Schema

`src/agent/state.py` extends `MessagesState` (which gives the accumulating
`messages` field) with the OODA-specific fields. Grouped by which node writes
each field.

```mermaid
classDiagram
    class MessagesState
    class OODAState
    MessagesState <|-- OODAState

    class OODAState {
        +str user_id
        +str session_id
        +list raw_events
        +dict telemetry_window
        +dict learner_profile
        +dict concept_state
        +list diagnosed_struggles
        +float engagement_score
        +dict selected_intervention
        +list intervention_candidates
        +bool exploration_flag
        +dict intervention_delivered
        +str delivery_channel
        +int cycle_count
        +str last_cycle_timestamp
        +bool should_pause
        +int max_cycles
        +list messages
    }
```

| Field group | Written by | Read by |
|---|---|---|
| `user_id`, `session_id` | `create_initial_state()` | All nodes |
| `raw_events`, `telemetry_window` | ARQ worker / aggregator | observe |
| `learner_profile`, `diagnosed_struggles`, `engagement_score`, `concept_state` | orient | decide, act |
| `selected_intervention`, `intervention_candidates`, `exploration_flag` | decide | act, pause |
| `intervention_delivered`, `delivery_channel`, `cycle_count`, `last_cycle_timestamp` | act | frontend, next cycle |
| `should_pause`, `max_cycles` | pause / `create_initial_state()` | decide_router |

---

## 5.4 — OBSERVE Node

```mermaid
flowchart LR
    A["state.raw_events"] --> B["last_event"]
    C["state.telemetry_window"] --> D["30s/2m/5m metrics"]
    B --> E["build_observation_prompt()"]
    D --> E
    E --> F["observation_summary string"]
    F --> G["return {raw_events:[], observation_summary, telemetry_window}"]
    G --> H["drains queue — events aren't re-processed"]
```

Key invariant: `raw_events` is **cleared** after processing. This is a queue
drain pattern — events are processed exactly once.

---

## 5.5 — ORIENT Node (Diagnosis)

```mermaid
flowchart TB
    IN["state.observation_summary<br>state.learner_profile<br>state.concept_state"] --> P["format ORIENT_PROMPT"]
    P --> LLM["get_llm_for_purpose('reasoning')<br>(GPT-4o with fallback chain)"]
    LLM --> PARSE["parse_orient_response()<br>(JSON)"]
    PARSE --> OUT["{diagnosed_struggles,<br>engagement_score,<br>learner_profile delta,<br>concept_state delta,<br>narrative → messages[]}"]
    OUT --> NEXT["DECIDE reads<br>diagnosed_struggles"]
```

Tools the ORIENT node may invoke via the LLM (Phase 5 §5.8 in the existing
docs):
- `mastery_tools.get_mastery`
- `mastery_tools.get_or_create_profile`
- `concept_tools.traverse_prerequisites`
- `wisdom_tools.get_community_insight`
- `delivery_tools.get_intervention_history`

---

## 5.6 — DECIDE Node (Thompson Sampling)

```mermaid
flowchart TB
    IN["state.diagnosed_struggles<br>state.learner_profile<br>state.engagement_score"] --> SEL["InterventionSelector.select()<br>(Phase 7)"]
    SEL --> CAND["candidates[]<br>(each has alpha, beta_param)"]
    CAND --> L1["for each candidate:<br>sample = np.random.beta(alpha, beta_param)"]
    L1 --> L2["best_arm = argmax sample"]
    L2 --> EXP["exploration_flag = total_trials < 10"]
    L2 --> OUT["{selected_intervention,<br>intervention_candidates,<br>exploration_flag,<br>messages: action+rationale}"]
    EXP --> OUT
```

Thompson sampling intuition: each arm's posterior is `Beta(α, β)`. Drawing a
sample and picking the max gives **automatic explore-vs-exploit** — the
agent explores early when posteriors are flat and exploits once posteriors
concentrate around the true win-rate.

---

## 5.7 — ACT Node (Delivery)

```mermaid
flowchart TB
    IN["state.selected_intervention"] --> CH{"exploration?"}
    CH -- Yes --> DROP["delivery_channel = 'none'<br>(safe exploration)"]
    CH -- No --> GEN["LLM generate payload<br>(reasoning model)"]
    GEN --> LOG["InterventionRepo.create()<br>(persist log)"]
    DROP --> LOG
    GEN --> DEL["DeliveryManager.send()<br>(WS / SSE)"]
    LOG --> INC["cycle_count++<br>last_cycle_timestamp = now"]
    INC --> RET["return {intervention_delivered,<br>delivery_channel, cycle_count+1, ...}"]
    DEL --> RET
```

The "safe exploration" pattern: arms with `<10` trials are **logged but not
delivered** to the student. Once enough data exists they go live.

---

## 5.8 — PAUSE Node (Cooldown)

```mermaid
flowchart TD
    A["state.last_cycle_timestamp"] --> B{"elapsed < cooldown?"}
    B -- Yes --> P["return {should_pause: True}<br>(skips act this cycle)"]
    B -- No --> C["return {should_pause: False}<br>(act can run)"]
    P --> R["decide_router -> pause branch next cycle"]
    C --> R2["decide_router -> act branch next cycle"]
```

Cooldown defaults to **30 s** (and is also controlled by the
`intervention_cooldown_seconds` setting). Prevents notification flooding.

---

## 5.9 — Checkpointer Strategy (Persistence)

```mermaid
flowchart TB
    A["_get_checkpointer()"] --> B{"DB reachable?"}
    B -- Yes --> PG["AsyncPostgresSaver<br>(survives restart)"]
    B -- No --> MS["MemorySaver<br>(per-process fallback)"]
    PG --> C["builder.compile(checkpointer=...)"]
    MS --> C
    C --> AG["Compiled agent<br>(singleton per process)"]
```

The `.replace("+asyncpg", "")` is critical — `AsyncPostgresSaver` expects a
plain `postgresql://` URL, not the SQLAlchemy `+asyncpg` form.

---

## 5.10 — Tool Surface Available to the LLM

```mermaid
flowchart LR
    subgraph TOOLS["src/agent/tools/"]
        T1["mastery_tools.get_mastery"]
        T2["mastery_tools.get_or_create_profile"]
        T3["concept_tools.traverse_prerequisites"]
        T4["delivery_tools.get_intervention_history"]
        T5["delivery_tools.log_intervention_result"]
        T6["wisdom_tools.get_community_insight"]
        T7["pacing_tools.adjust_pacing"]
        T8["generation_tools.generate_challenge_explanation"]
    end
    LLM["ORIENT/ACT LLM call"] --> T1 & T2 & T3 & T4 & T5 & T6 & T7 & T8
    T1 & T2 --> REPO1["LearnerProfileRepo"]
    T3 --> CG["ConceptRepo / queries.py"]
    T4 & T5 --> REPO2["InterventionRepo"]
    T6 --> GW["GlobalWisdomService"]
    T8 --> GEN["InterventionGenerator"]
```

---

## 5.11 — Prompt Files and Where They Are Used

```mermaid
flowchart LR
    P1["orient_prompt.py"] --> OR["orient_node"]
    P2["decide_prompt.py"] --> DC["decide context"]
    P3["generate_prompt.py"] --> AC["act_node"]
    P4["explain_prompt.py"] --> TOOL["generation_tools"]
    OR -- "ORIENT_SYSTEM_PROMPT + user prompt" --> OUT1["structured JSON:<br>struggles, engagement, narrative"]
    AC -- "ACT_SYSTEM_PROMPT + user prompt" --> OUT2["personalized intervention text"]
```

---

## 5.12 — Phase 5 Component Map

```mermaid
flowchart TB
    subgraph P5["src/agent/"]
        ST["state.py<br>(OODAState)"]
        GR["graph.py<br>(build_ooda_graph, compile_ooda_agent, create_initial_state)"]
        ND["nodes/<br>observe, orient, decide, act, pause, decide_router"]
        TL["tools/<br>mastery, concept, wisdom, delivery, generation, pacing, logging"]
        PR["prompts/<br>orient, decide, generate, explain"]
    end
    CFG["config/settings.py<br>(max_cycles, intervention_cooldown_seconds)"]
    CKPT["langgraph.checkpoint.postgres<br>(or MemorySaver fallback)"]
    ST --> GR
    ND --> GR
    GR --> CKPT
    GR --> CFG
    PR --> ND
    TL --> ND
```
