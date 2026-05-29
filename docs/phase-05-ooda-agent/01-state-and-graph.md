# Phase 5 — OODA Agent Core

## System Design Reference

Master System Design, "Agent Core" section. The design specified a LangGraph StateGraph with 5 nodes (Observe, Orient, Decide, Act, Pause) running in a continuous loop, with conditional routing and PostgreSQL checkpointing.

---

## Task 5.1: State Definition (`src/agent/state.py`)

### Purpose

Defines `OODAState`, the typed state schema that flows through the OODA graph. Every node reads from and writes to this state. It extends LangGraph's `MessagesState` which provides built-in message accumulation.

### Line-by-Line Explanation

```python
import operator
from typing import Annotated, Any
from langgraph.graph import MessagesState
```

- `operator` — Python's operator module. `operator.add` is used as a reducer for list fields.
- `Annotated` — Type annotation that carries additional metadata (used by LangGraph for reducer functions).
- `MessagesState` — LangGraph's pre-built state class with a `messages: list` field that uses `operator.add` as reducer.

```python
class OODAState(MessagesState):
    user_id: str
    session_id: str
```

**Identity fields.** Every state belongs to one user session. These don't change during the OODA loop.

```python
    raw_events: list[dict[str, Any]]
    telemetry_window: dict[str, Any]
```

**OBSERVE inputs** (written by the event pipeline, consumed by OBSERVE node):
- `raw_events` — Queued student events waiting to be processed
- `telemetry_window` — Pre-computed telemetry from `TelemetryAggregator`

```python
    learner_profile: dict[str, Any]
    concept_state: dict[str, Any]
    diagnosed_struggles: list[str]
    engagement_score: float
```

**ORIENT outputs** (computed by ORIENT, consumed by DECIDE):
- `learner_profile` — Full profile with mastery_map, learning_style, etc.
- `concept_state` — Current mastery state per concept
- `diagnosed_struggles` — List of concept IDs the learner is struggling with
- `engagement_score` — 0.0 (disengaged) to 1.0 (highly engaged)

```python
    selected_intervention: dict[str, Any] | None
    intervention_candidates: list[dict[str, Any]]
    exploration_flag: bool
```

**DECIDE outputs:**
- `selected_intervention` — The chosen intervention (type, concept, rationale)
- `intervention_candidates` — All candidate arms with Thompson samples
- `exploration_flag` — True if the chosen candidate has <10 trials (exploration vs exploitation)

```python
    intervention_delivered: dict[str, Any] | None
    delivery_channel: str
```

**ACT outputs:**
- `intervention_delivered` — The full intervention payload
- `delivery_channel` — `"websocket"`, `"sse"`, or `"none"`

```python
    cycle_count: int
    last_cycle_timestamp: str
    should_pause: bool
    max_cycles: int
```

**Loop control:**
- `cycle_count` — Number of complete OODA cycles. Incremented by ACT.
- `last_cycle_timestamp` — When the last cycle completed. Used by PAUSE for cooldown.
- `should_pause` — Set by PAUSE when cooldown is active. Read by `decide_router`.
- `max_cycles` — Termination condition. When `cycle_count >= max_cycles`, the graph routes to END.

```python
    messages: Annotated[list, operator.add]
```

**Message accumulator.** Uses `operator.add` as reducer, meaning each node's messages are APPENDED to the list rather than replacing it. This preserves the full execution trace across cycles.

### How It Connects

```
             OODAState flows through the graph:
START → {raw_events, cycle_count=0}
  OBSERVE → adds telemetry_window, _derived_signals
  ORIENT  → adds learner_profile, diagnosed_struggles, engagement_score
  DECIDE  → adds selected_intervention, intervention_candidates
  ACT     → adds intervention_delivered, increments cycle_count
  PAUSE   → sets should_pause (if cooldown active)
  → back to OBSERVE (or END if max_cycles reached)
```

---

## Task 5.2: Graph Wiring (`src/agent/graph.py`)

### Purpose

Builds and compiles the LangGraph StateGraph. Defines all nodes, edges, and conditional routing. Also provides the checkpointer (PostgreSQL with MemorySaver fallback) and `create_initial_state()` factory.

### Line-by-Line (full explanation already given in conversation, condensed here)

**Checkpointer (lines 22-42):**
```python
def _get_checkpointer():
    global _CHECKPOINTER
    if _CHECKPOINTER is not None:
        return _CHECKPOINTER
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        settings = get_settings()
        cp = AsyncPostgresSaver.from_conn_string(
            settings.database_url.replace("+asyncpg", "")
        )
        _CHECKPOINTER = cp
    except Exception as e:
        logger.warning("Postgres checkpointer unavailable (%s), using MemorySaver fallback", e)
        from langgraph.checkpoint.memory import MemorySaver
        _CHECKPOINTER = MemorySaver()
    return _CHECKPOINTER
```

**Design decision:** The `.replace("+asyncpg", "")` is needed because `AsyncPostgresSaver.from_conn_string()` expects a regular `postgresql://` URL, not `postgresql+asyncpg://`. The `+asyncpg` is SQLAlchemy-specific.

The entire try/except is the **graceful degradation pattern**: if PostgreSQL is unavailable, the agent still compiles with an in-memory checkpointer. The checkpointer only affects state persistence across restarts — the agent works fine without it.

**Continue Router (lines 45-51):**
```python
def continue_router(state: OODAState) -> str:
    max_cycles = state.get("max_cycles", 9999)
    current = state.get("cycle_count", 0)
    if current >= max_cycles:
        logger.info("Reached max_cycles=%d at cycle_count=%d, ending", max_cycles, current)
        return "end"
    return "orient"
```

Returns `"end"` (→ END) or `"orient"` (→ ORIENT node). The `max_cycles` parameter was added to fix the infinite loop bug — without it, the graph would cycle forever. Default 9999 means production use is effectively unlimited.

**Graph Construction (lines 54-70):**
```python
def build_ooda_graph() -> StateGraph:
    builder = StateGraph(OODAState)
    builder.add_node("observe", observe_node)
    builder.add_node("orient", orient_node)
    builder.add_node("decide", decide_node)
    builder.add_node("act", act_node)
    builder.add_node("pause", pause_node)

    builder.add_edge(START, "observe")
    builder.add_conditional_edges("observe", continue_router, {"orient": "orient", "end": END})
    builder.add_edge("orient", "decide")
    builder.add_conditional_edges("decide", decide_router, ["act", "pause"])
    builder.add_edge("act", "observe")
    builder.add_edge("pause", "observe")
    return builder
```

The graph topology:
1. START → observe (entry point)
2. observe → (conditional) orient or END
3. orient → decide (always)
4. decide → (conditional) act or pause
5. act → observe (loop back)
6. pause → observe (loop back with cooldown)

**compile_ooda_agent (lines 73-84):**
```python
async def compile_ooda_agent():
    builder = build_ooda_graph()
    checkpointer = _get_checkpointer()
    if hasattr(checkpointer, "setup"):
        try:
            await checkpointer.setup()
        except Exception:
            pass
    agent = builder.compile(checkpointer=checkpointer)
    return agent
```

Compiles the graph with the checkpointer. The `.setup()` call is specific to `AsyncPostgresSaver` (initializes the checkpoint table). MemorySaver has no setup.

**create_initial_state (lines 87-111):**
```python
async def create_initial_state(
    user_id: str, session_id: str, max_cycles: int = 9999
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "session_id": session_id,
        "raw_events": [],
        "telemetry_window": {},
        # ... all fields initialized to defaults ...
        "max_cycles": max_cycles,
    }
```

Factory function that creates a fresh state. Called at the start of every session. The raw state dict is converted to `OODAState` by LangGraph at runtime.

### How It Connects

```
demo.py → build_ooda_graph() → graph.compile() → agent.ainvoke(state)
web_demo.py → same pattern
interactive_demo.py → same pattern (runs on each button click)
src/api/routers/agent.py → compile_ooda_agent() (for server-managed sessions)
```
