# Phase 8 — API Layer: System Design Diagrams

The API layer is the **only public surface** of the system. It maps HTTP,
WebSocket, and SSE requests to OODA cycles, event ingestion, telemetry
streaming, and intervention delivery.

---

## 8.1 — FastAPI Application Topology

```mermaid
flowchart TB
    subgraph LIFESPAN["lifespan(ctx)"]
        S1["app.state.redis = aioredis.from_url()"]
        S2["compile_ooda_agent() → app.state.agent"]
        S3["app.state.session_cache = SessionCache(redis)"]
        S4["app.state.stream_consumer = RedisStreamConsumer(redis)"]
    end

    subgraph MIDDLEWARE["Middleware"]
        CORS["CORSMiddleware (allow *)"]
    end

    subgraph ROUTERS["Routers (all under /api/v1/ai)"]
        R1["events_router"]
        R2["telemetry_router"]
        R3["interventions_router"]
        R4["agent_router"]
        R5["concept_graph_router"]
    end

    HEALTH["GET /health"]
    LIFESPAN --> MIDDLEWARE --> ROUTERS
    LIFESPAN --> MIDDLEWARE --> HEALTH
```

---

## 8.2 — Router Map

```mermaid
flowchart LR
    subgraph EVENTS["events_router"]
        E1["POST /events"]
        E2["POST /events/batch"]
        E3["POST /domain-events"]
    end
    subgraph TELEMETRY["telemetry_router"]
        T1["WS /telemetry/ws"]
    end
    subgraph INT["interventions_router"]
        I1["WS /interventions/{user_id}/ws"]
        I2["GET /interventions/{user_id}/stream"]
    end
    subgraph AGENT["agent_router"]
        A1["POST /agent/sessions/{user_id}/start"]
        A2["POST /agent/sessions/{user_id}/cycle"]
        A3["POST /agent/sessions/{user_id}/stop"]
        A4["GET /agent/sessions/{user_id}/state"]
    end
    subgraph CONCEPT["concept_graph_router"]
        C1["GET /concepts/{id}"]
        C2["GET /concepts/{id}/neighbors?depth=2"]
        C3["GET /concepts/{id}/prerequisites"]
        C4["GET /concepts/search?query=..."]
    end
```

All routers are mounted under the `/api/v1/ai` prefix in `app.py`.

---

## 8.3 — Event Ingestion Path

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant FastAPI
    participant Schema as Pydantic Schema
    participant Consumer as RedisStreamConsumer
    participant Redis

    Client->>FastAPI: POST /api/v1/ai/events (json)
    FastAPI->>Schema: ObservationEventPayload(**body)
    alt validation fails
        Schema-->>FastAPI: ValidationError
        FastAPI-->>Client: 422 with field errors
    else valid
        Schema-->>FastAPI: validated payload
        FastAPI->>Consumer: push_observation(payload.model_dump())
        Consumer->>Redis: XADD ai:observations * data=...
        Redis-->>Consumer: msg_id
        Consumer-->>FastAPI: msg_id
        FastAPI-->>Client: {status: ok, message_id: msg_id}
    end
```

---

## 8.4 — Telemetry WebSocket Loop

```mermaid
sequenceDiagram
    autonumber
    participant Browser
    participant WS as FastAPI WebSocket
    participant Sch as TelemetryEventPayload
    participant Con as RedisStreamConsumer
    participant Red as Redis

    Browser->>WS: connect ws://host/api/v1/ai/telemetry/ws
    WS->>Browser: accept
    loop streaming
        Browser->>WS: send_json(telemetry)
        WS->>Sch: TelemetryEventPayload(**data)
        Sch-->>WS: validated
        WS->>Con: push_telemetry(data)
        Con->>Red: XADD ai:telemetry * ...
        Red-->>Con: msg_id
        WS->>Browser: {status: ok, message_id}
    end
    Browser-->>WS: disconnect
    WS->>WS: log "Telemetry WebSocket disconnected"
```

---

## 8.5 — Agent Cycle Endpoint (The Core API)

This endpoint ties session cache + OODA graph + intervention delivery
together. It is the **primary API** used by the demos and (in production) by
the front-end.

```mermaid
sequenceDiagram
    autonumber
    participant FE as Frontend
    participant API as /agent/sessions/{user_id}/cycle
    participant Cache as SessionCache (Redis)
    participant Con as StreamConsumer (Redis)
    participant Agent as LangGraph Agent
    participant Repo as Repositories
    participant WS as Intervention WebSocket

    FE->>API: POST /cycle
    API->>Cache: get_state(user_id)
    alt no active session
        Cache-->>API: None
        API-->>FE: {status: error, message: start a session first}
    else session exists
        Cache-->>API: state
        API->>Con: pop_events(user_id)
        Con-->>API: events[]
        API->>Agent: agent.ainvoke(state + events)
        Agent->>Repo: read profile, wisdom, etc.
        Agent-->>API: result {intervention_delivered, cycle_count, ...}
        API->>Cache: set_state(user_id, result)
        opt intervention ready
            API->>WS: deliver via _active_connections[user_id]
        end
        API-->>FE: {status: completed, cycle, intervention, diagnosis, engagement}
    end
```

---

## 8.6 — Intervention Delivery WebSocket

```mermaid
sequenceDiagram
    autonumber
    participant Browser
    participant WS as /interventions/{user_id}/ws
    participant Mgr as connect_websocket()
    participant ACT as ACT node
    participant Con as _active_connections[user_id]

    Browser->>WS: connect
    WS->>Mgr: connect_websocket(user_id, ws)
    Mgr->>Con: append ws to user's list
    Note over ACT: On a later OODA cycle:<br>intervention chosen
    ACT->>Con: deliver_via_websocket(user_id, payload)
    Con->>WS: ws.send_json(payload) for every open socket
    WS-->>Browser: {intervention_id, type, content, ...}
    Browser-->>WS: ping (heartbeat)
    WS-->>Browser: {type: pong}
    Browser-->>WS: disconnect
    WS->>Mgr: disconnect_websocket(user_id, ws)
```

A user can have **multiple browser tabs** open — every active socket in
`_active_connections[user_id]` receives the message. Closed sockets are
pruned automatically.

---

## 8.7 — Concept Graph Endpoints

```mermaid
flowchart LR
    G1["GET /concepts/{id}"] --> R1["ConceptRepo.get()"]
    G2["GET /concepts/{id}/neighbors?depth=2"] --> R2["ConceptRepo.get_with_neighbors()"]
    G3["GET /concepts/{id}/prerequisites"] --> R3["queries.get_prerequisite_chain()<br>(recursive CTE)"]
    G4["GET /concepts/search?query=..."] --> R4["generate_embedding()<br>+ ConceptRepo.search_similar()<br>(pgvector)"]
```

---

## 8.8 — Dependency Injection

```mermaid
flowchart LR
    subgraph DI["src/api/dependencies.py"]
        D1["get_stream_consumer()"]
        D2["get_session_cache()"]
        D3["get_session_factory()"]
    end
    R1["events_router"] --> D1
    R2["telemetry_router"] --> D1
    R3["interventions_router"] -.->|state| D2
    R4["agent_router"] --> D2
    R5["concept_graph_router"] -.->|direct| REPO["ConceptRepo()"]
    D1 --> REDIS["app.state.redis"]
    D2 --> REDIS
```

DI keeps handlers thin and testable. Each handler receives its collaborators
via `Depends()`.

---

## 8.9 — Middleware & Exception Handlers

```mermaid
flowchart TB
    REQ["HTTP Request"] --> M1["CORS<br>(allow all origins)"]
    M1 --> M2["Request logging middleware<br>(method, path, status, latency)"]
    M2 --> EH1{{"ValidationError?"}}
    EH1 -- Yes --> R1["422 JSON with field errors"]
    EH1 -- No --> EH2{{"AB6AIError?"}}
    EH2 -- Yes --> R2["structured error response"]
    EH2 -- No --> R3["handler executes"]
    R3 --> RES["HTTP Response"]
    RES --> M2
```

---

## 8.10 — Phase 8 Component Map

```mermaid
flowchart TB
    subgraph P8["src/api/"]
        A["app.py<br>(create_app + lifespan)"]
        D["dependencies.py<br>(get_stream_consumer, get_session_cache)"]
        M["middleware/sanitizer.py<br>(PII strip on inbound)"]
        R["routers/<br>events, telemetry, interventions, agent, concept_graph"]
    end
    subgraph BACK["Backend resources"]
        REDIS[("Redis")]
        AGENT["Compiled OODA Agent"]
        REPO["Repositories"]
        WS["Intervention WS manager"]
    end
    A --> R
    A --> D
    D --> REDIS
    A --> AGENT
    R --> REPO
    R --> WS
    M --> R
```
