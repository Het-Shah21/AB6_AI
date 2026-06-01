# Phase 3 — Event Pipeline: System Design Diagrams

Phase 3 builds the **event spine** of the system. Every student action (HTTP
event, telemetry WebSocket, domain event) flows through Redis Streams, gets
processed by an ARQ worker, and ends up in the OBSERVE node's `raw_events`
queue.

---

## 3.1 — End-to-End Event Flow

```mermaid
flowchart LR
    subgraph CLIENT["Client (browser / robot)"]
        U["Student event<br>(HTTP POST)"]
        T["Telemetry stream<br>(WebSocket)"]
    end

    subgraph API["src/api/"]
        EVR["routers/events.py"]
        TR["routers/telemetry.py"]
    end

    subgraph ING["src/ingestion/"]
        SCH["schemas.py<br>(Pydantic validation)"]
        CON["consumer.py<br>(RedisStreamConsumer)"]
        AGG["aggregator.py<br>(TelemetryAggregator)"]
        WRK["worker.py<br>(ARQ process)"]
    end

    subgraph REDIS["Redis 7"]
        S1["ai:observations<br>(Stream)"]
        S2["ai:telemetry<br>(Stream)"]
        S3["ai:domain_events<br>(Stream)"]
        L1["user:{id}:events<br>(List, capped 100)"]
    end

    U -->|"POST /events"| EVR
    T -->|"WS /telemetry/ws"| TR
    EVR --> SCH
    TR --> SCH
    SCH --> CON
    CON -->|"XADD"| S1
    CON -->|"XADD"| S2
    CON -->|"XADD"| S3
    S1 -->|"XREADGROUP"| WRK
    S2 -->|"XREADGROUP"| WRK
    S3 -->|"XREADGROUP"| WRK
    WRK --> AGG
    WRK -->|"LPUSH + LTRIM 100"| L1
    L1 -->|"OODA Observe<br>raw_events"| OODA["Phase 5 — OODA Agent"]
    AGG -->|"telemetry_window"| OODA
```

---

## 3.2 — Telemetry Windowing

`TelemetryAggregator` keeps **3 rolling time windows per user** (30 s, 2 min,
5 min). Older data is evicted on every append. This is the data the OBSERVE
node consumes each cycle.

```mermaid
flowchart TB
    EV["incoming telemetry dict"] --> ADD["add_data(user_id, ev)"]
    ADD --> W1["30s window<br>(near real-time)"]
    ADD --> W2["2m window<br>(short-term trend)"]
    ADD --> W3["5m window<br>(medium-term trend)"]
    W1 --> AGG["aggregate(user_id)"]
    W2 --> AGG
    W3 --> AGG
    AGG --> OUT["{ '30s': {smoothness, imu_samples, joint_samples},<br>'2m': {...}, '5m': {...} }"]
    OUT --> OBS["OBSERVE node reads<br>telemetry_window from state"]
```

---

## 3.3 — ARQ Worker Lifecycle

```mermaid
sequenceDiagram
    autonumber
    participant W as ARQ Worker
    participant RS as Redis Stream
    participant AGG as TelemetryAggregator
    participant RL as Redis List
    participant OBS as OODA Observe

    loop while running
        W->>RS: XREADGROUP ai:observations
        RS-->>W: batch of new events
        W->>W: enrich with enriched_at, derived fields
        alt event is video_play / pause / seek
            W->>AGG: update(user_id, telemetry)
        end
        W->>RL: LPUSH user:{id}:events (json)
        W->>RL: LTRIM 0 99  (cap at 100)
        W->>RS: XACK (acknowledge)
    end

    Note over OBS: Next OODA cycle<br>reads from RL via state.raw_events
```

---

## 3.4 — Redis Stream Consumer Group Setup

Consumer groups make event processing **reliable and parallelizable**.
Multiple workers can run without losing events.

```mermaid
sequenceDiagram
    participant P as Producer (API)
    participant R as Redis Stream
    participant W1 as Worker 1
    participant W2 as Worker 2

    P->>R: XADD ai:observations * data=...
    Note over R: xgroup_create<br>(mkstream=True, id=0)
    P->>R: XADD ai:observations * data=...
    par parallel consumption
        W1->>R: XREADGROUP g1 w1 COUNT 10 BLOCK 2000
        R-->>W1: [event-1, event-2]
    and
        W2->>R: XREADGROUP g1 w2 COUNT 10 BLOCK 2000
        R-->>W2: [event-3]
    end
    W1->>R: XACK event-1 event-2
    W2->>R: XACK event-3
```

---

## 3.5 — Stream Names and Their Producers / Consumers

```mermaid
flowchart LR
    subgraph P1["Observations"]
        S1["ai:observations"]
        P1A["events.py<br>POST /events"]
        C1A["worker.py<br>process_observation"]
    end
    subgraph P2["Telemetry"]
        S2["ai:telemetry"]
        P2A["telemetry.py<br>WS /telemetry/ws"]
        C2A["worker.py<br>process_telemetry"]
    end
    subgraph P3["Domain"]
        S3["ai:domain_events"]
        P3A["events.py<br>POST /domain-events"]
        C3A["worker.py<br>process_domain_event"]
    end

    P1A --> S1 --> C1A
    P2A --> S2 --> C2A
    P3A --> S3 --> C3A
```

Stream names are defined as constants in `src/config/settings.py` and
re-exported from `src/ingestion/schemas.py`.

---

## 3.6 — Schema Validation Boundary

The Pydantic models in `ingestion/schemas.py` are the **only** types allowed
across the API → Redis boundary. Invalid requests are rejected with a 422
before they ever reach Redis.

```mermaid
flowchart LR
    REQ["HTTP Request body"] --> P["ObservationRequest<br>(Pydantic)"]
    P -->|"Field(ge=0, le=1)<br>for score"| OK1{{"Valid?"}}
    OK1 -- No --> R422["422 Unprocessable Entity<br>(rejected at the edge)"]
    OK1 -- Yes --> PUSH["RedisStreamConsumer.push_observation()"]
    PUSH --> REDIS["ai:observations"]
```

---

## 3.7 — Phase 3 Component Map

```mermaid
flowchart TB
    subgraph P3["src/ingestion/"]
        S["schemas.py<br>(3 Pydantic payloads + 3 stream-name consts)"]
        C["consumer.py<br>(RedisStreamConsumer)"]
        A["aggregator.py<br>(TelemetryAggregator)"]
        W["worker.py<br>(ARQ WorkerSettings)"]
    end
    SH["src/shared/events.py<br>(internal event models)"]
    TM["src/shared/telemetry_math.py<br>(pure math)"]
    C --> S
    A --> TM
    W --> A
    W --> C
```
