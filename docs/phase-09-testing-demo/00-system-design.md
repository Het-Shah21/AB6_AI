# Phase 9 — Testing & Demo: System Design Diagrams

Phase 9 covers the **verification and presentation** layer: 21 unit tests that
guard the contracts established in Phases 1–8, and three demo scripts
(CLI, web, interactive) that exercise the full OODA loop end-to-end.

---

## 9.1 — Test Categories at a Glance

```mermaid
flowchart TB
    subgraph T["tests/ (21 tests across 5 files)"]
        T1["test_ingestion.py<br/>(4 tests)"]
        T2["test_concept_graph.py<br/>(4 tests)"]
        T3["test_agent.py<br/>(5 tests)"]
        T4["test_intervention.py<br/>(4 tests)"]
        T5["test_memory.py<br/>(4 tests)"]
    end
    T1 --> P3["Phase 3 — Event Pipeline"]
    T2 --> P4["Phase 4 — Concept Graph"]
    T3 --> P5["Phase 5 — OODA Agent"]
    T4 --> P7["Phase 7 — Intervention Engine"]
    T5 --> P6["Phase 6 — Dual Memory"]
```

Each test file maps to **exactly one** of the implementation phases. The
correspondence is what makes regressions easy to localize.

---

## 9.2 — Test Fixture Map

```mermaid
flowchart LR
    subgraph CF["conftest.py"]
        F1["mock_redis<br/>(FakeRedis)"]
        F2["mock_session<br/>(AsyncMock SQLAlchemy)"]
        F3["mock_llm<br/>(returns fixed JSON)"]
        F4["test_settings<br/>(test DB URL override)"]
    end
    F1 --> T1
    F2 --> T2
    F3 --> T3
    F3 --> T4
    F2 --> T5
    F4 --> T1 & T2 & T3 & T4 & T5
```

| Fixture | Phase covered | Replaces |
|---|---|---|
| `mock_redis` | Phase 3 | Real Redis (in-memory fake) |
| `mock_session` | Phases 1, 4, 6, 7 | Real PostgreSQL (AsyncMock) |
| `mock_llm` | Phases 2, 5, 7 | OpenAI / Anthropic / Google (returns canned JSON) |
| `test_settings` | All | Pydantic settings pointing at test DB |

---

## 9.3 — The 5 Test That Matter Most

### 9.3.1 — End-to-End OODA Cycle (regression guard)

```mermaid
sequenceDiagram
    autonumber
    participant T as test_one_ooda_cycle
    participant AG as compile_ooda_agent()
    participant ST as create_initial_state(max_cycles=1)
    participant IN as LangGraph runtime
    T->>AG: compile graph
    T->>ST: build initial state with one event
    T->>IN: agent.ainvoke(state)
    IN-->>T: result
    T->>T: assert cycle_count >= 1<br/>assert 'messages' in result
    T-->>T: PASS in <60s
```

> This test **specifically guards** against the historic infinite-loop bug.
> It was the regression test added when the `continue_router` was wired in.

### 9.3.2 — Thompson Sampling Monte Carlo

```mermaid
flowchart LR
    A["3 arms:<br/>A hint Beta(6,5)<br/>B video Beta(2,9)<br/>C practice Beta(10,1)"] --> L["loop 1000 times"]
    L --> S["draw 1 sample from each Beta"]
    S --> M["argmax of 3 samples"]
    M --> C["Counter of which arm won"]
    C --> A2["assert C > A and C > B"]
```

The arm with the **highest true success rate** (practice, 91%) is the
modal winner over 1000 trials — verifying the sampling distribution.

### 9.3.3 — Pydantic Validation at the Edge

```mermaid
flowchart TB
    A["ObservationRequest(event_type='end_attempt', score=1.5)"] --> B["Field(ge=0.0, le=1.0)"]
    B --> C["raises ValidationError"]
    C --> D["pytest.raises(ValidationError) catches it"]
    D --> E["PASS"]
```

### 9.3.4 — Recursive CTE Walks Correctly

```mermaid
flowchart LR
    A["ik-inverse-kinematics"] --> B["level 1: forward-kinematics"]
    B --> C["level 2: coordinate-systems"]
    C --> D["level 3: basic-trigonometry"]
    D --> E["assert chain[0]['level'] >= 3"]
    E --> F["assert all depths unique"]
```

### 9.3.5 — Schema Defaults (Initial State)

```mermaid
flowchart TB
    A["create_initial_state('u1','s1')"] --> B["assert user_id == 'u1'"]
    A --> C["assert cycle_count == 0"]
    A --> D["assert raw_events == []"]
    A --> E["assert max_cycles == 9999"]
    A --> F["assert engagement_score == 0.5"]
    B & C & D & E & F --> G["PASS"]
```

---

## 9.4 — Demo Scripts Side by Side

```mermaid
flowchart TB
    subgraph CLI["demo.py"]
        C1["argparse: --user-id, --session-id, --max-cycles, --event"]
        C2["build state + add mock event"]
        C3["agent.ainvoke(state)"]
        C4["print cycle trace (color)"]
        C1 --> C2 --> C3 --> C4
    end

    subgraph WEB["web_demo.py"]
        W1["GET /"]
        W2["hardcoded demo data"]
        W3["agent.ainvoke()"]
        W4["render full OODA state as HTML"]
        W1 --> W2 --> W3 --> W4
    end

    subgraph INT["interactive_demo.py"]
        I1["GET /  → form with event buttons"]
        I2["POST /run  → append event + cycle"]
        I3["POST /reset → clear session"]
        I4["session state in dict keyed by UUID"]
        I1 --> I2 --> I3
        I2 --> I4
    end
```

| Demo | Audience | Interaction | Persistence |
|---|---|---|---|
| `demo.py` | Developers | CLI args only | None — single cycle |
| `web_demo.py` | Quick visual check | None | None |
| `interactive_demo.py` | Live presentation | Form buttons | In-memory dict |

---

## 9.5 — Test Pyramid

```mermaid
flowchart TB
    subgraph TOP["E2E (interactive_demo)"]
        T1["Live OODA cycle in browser"]
    end
    subgraph MID["Integration (test_one_ooda_cycle)"]
        M1["Compile graph + run 1 cycle + assert"]
    end
    subgraph BOT["Unit (other 20 tests)"]
        B1["Schemas / CTEs / Thompson / Repos"]
    end
    TOP --> MID --> BOT
    style TOP fill:#fee2e2
    style MID fill:#fef3c7
    style BOT fill:#dcfce7
```

The 21 unit tests sit at the base; the integration test (`test_one_ooda_cycle`)
sits one level up; the interactive demo is the manual E2E at the top.

---

## 9.6 — Bugs Fixed (And Their Guarding Tests)

```mermaid
flowchart LR
    B1["Infinite OODA loop<br/>(no max_cycles)"] --> F1["Fix: continue_router + max_cycles=9999"]
    F1 --> T1["test_one_ooda_cycle (max_cycles=1)"]
    B2["web_demo button did nothing"] --> F2["Fix: SSR replaces JS onclick"]
    F2 --> T2["manual click in interactive_demo"]
    B3["NAME_PATTERN over-matched<br/>(caught 'Inverse Kinematics')"] --> F3["Fix: require 'name:'/'user:'/'student:' prefix"]
    F3 --> T3["implicit in event-validation tests"]
```

---

## 9.7 — How Tests Run

```mermaid
flowchart LR
    A["pytest tests/ -v"] --> B["auto-discovers test_*.py"]
    B --> C["asyncio_mode=auto<br/>(no @pytest.mark.asyncio needed)"]
    C --> D["runs 21 tests"]
    D --> E["exit 0 on pass"]
    D --> F["exit 1 + traceback on fail"]
    G["pytest tests/ --cov=src"] --> H["adds line coverage report"]
    A --> G
```

---

## 9.8 — CI View (Conceptual)

```mermaid
flowchart LR
    PUSH["git push"] --> LINT["ruff check src/"]
    LINT --> TYPE["mypy src/ (strict)"]
    TYPE --> UNIT["pytest tests/unit/ -v"]
    UNIT --> BUILD["docker build"]
    BUILD --> DEPLOY["deploy to staging"]
```

This is the suggested CI pipeline; only the test step is implemented in-repo
(`pyproject.toml` declares `asyncio_mode = "auto"`).

---

## 9.9 — Phase 9 Component Map

```mermaid
flowchart LR
    subgraph T["tests/"]
        T1["test_ingestion.py"]
        T2["test_concept_graph.py"]
        T3["test_agent.py"]
        T4["test_intervention.py"]
        T5["test_memory.py"]
    end
    subgraph D["Demos (root)"]
        D1["demo.py<br/>(CLI)"]
        D2["web_demo.py<br/>(SSR)"]
        D3["interactive_demo.py<br/>(form + WS)"]
    end
    subgraph CFG["pyproject.toml"]
        PM["asyncio_mode = auto<br/>testpaths = tests"]
    end
    CFG --> T
    T --> SRC["src/ (all phases)"]
    D --> SRC
```
