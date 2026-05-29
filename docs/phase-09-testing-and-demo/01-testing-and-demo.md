# Phase 9 — Testing & Demo

## System Design Reference

Master System Design, "Testing Strategy" and "Deployment" sections. Specified unit tests (21), integration tests, and demo scripts for PoC presentation.

---

## Task 9.1: Test Suite (`tests/`)

### 21 Tests Across 5 Categories

```python
tests/
├── test_ingestion.py      # 4 tests — schemas, consumer, aggregator, worker
├── test_concept_graph.py   # 4 tests — models, embeddings, builder, queries
├── test_agent.py           # 5 tests — state, graph, OODA flow, each node
├── test_intervention.py    # 4 tests — selector, generator, effectiveness, delivery
└── test_memory.py          # 4 tests — session cache, profile store, global wisdom, benchmarks
```

**Test 1: test_ingestion_schemas** (`test_ingestion.py:test_schemas`)
```python
async def test_observation_request_validation():
    # Valid request
    req = ObservationRequest(event_type="start_attempt", challenge_id="abc123")
    assert req.event_type == "start_attempt"
    
    # Invalid — score > 1.0
    with pytest.raises(ValidationError):
        ObservationRequest(event_type="end_attempt", score=1.5)
    
    # Invalid — bad event_type
    with pytest.raises(ValidationError):
        ObservationRequest(event_type="invalid_type")
```

Validates that Pydantic constraints reject bad data at the API boundary.

**Test 2: test_ingestion_consumer** (`test_ingestion.py:test_consumer`)
```python
async def test_redis_stream_push_and_read(mock_redis):
    consumer = RedisStreamConsumer(mock_redis)
    event_id = await consumer.push_event("test:stream", {"key": "value"})
    assert event_id is not None
    
    events = await consumer.read_events("test:stream", "test:group", "test:c")
    assert len(events) == 1
    assert events[0]["key"] == "value"
```

Uses `mock_redis` fixture — a fake Redis client that stores streams in-memory for testing.

**Test 3: test_agent_state** (`test_agent.py:test_state_schema`)
```python
async def test_ooda_state_defaults():
    state = await create_initial_state("user1", "session1")
    assert state["user_id"] == "user1"
    assert state["cycle_count"] == 0
    assert state["raw_events"] == []
    assert state["max_cycles"] == 9999
```

Verifies `create_initial_state()` produces correct defaults for all fields.

**Test 4: test_agent_full_cycle** (`test_agent.py:test_full_cycle`)
```python
async def test_one_ooda_cycle():
    agent = await compile_ooda_agent()
    state = await create_initial_state("user1", "session1", max_cycles=1)
    state["raw_events"] = [{"event_type": "wrong", "challenge_id": "ik_01"}]
    
    result = await agent.ainvoke(state)
    assert result["cycle_count"] >= 1
    assert "messages" in result
```

End-to-end test: compiles the graph, feeds one event, runs max_cycles=1, and checks the output. This is the test that catches infinite loop regressions.

**Test 5: test_thompson_sampling** (`test_intervention.py:test_thompson_sampling`)
```python
async def test_thompson_sampling():
    tracker = EffectivenessTracker(mock_session)
    arms = [
        InterventionArm(intervention_id="a", type="hint", concept_id="c1", success_count=5, trial_count=10),
        InterventionArm(intervention_id="b", type="video", concept_id="c1", success_count=1, trial_count=10),
        InterventionArm(intervention_id="c", type="practice", concept_id="c1", success_count=9, trial_count=10),
    ]
    
    selections = Counter()
    for _ in range(1000):
        samples = [np.random.beta(a.success_count + 1, a.trial_count - a.success_count + 1) for a in arms]
        best_idx = np.argmax(samples)
        selections[arms[best_idx].intervention_id] += 1
    
    # Arm C (practice, 90% success) should be selected most often
    assert selections["c"] > selections["a"]
    assert selections["c"] > selections["b"]
```

Statistical Monte Carlo test: verifies that after 1000 samples, the most effective arm is selected most frequently.

### Running Tests

```bash
# All tests
pytest tests/ -v

# Single category
pytest tests/test_agent.py -v --timeout=60

# With coverage
pytest tests/ --cov=src --cov-report=term-missing
```

### Test Fixtures

The `conftest.py` provides:
- `mock_redis` — FakeRedis instance for consumer tests
- `mock_session` — AsyncMock SQLAlchemy session for repo tests
- `mock_llm` — Returns fixed JSON responses for LLM-dependent tests
- `test_settings` — Overrides settings with test values (e.g., test database URL)

---

## Task 9.2: Demo Scripts

### demo.py — CLI Demo

```
usage: demo.py [-h] [--user-id USER_ID] [--session-id SESSION_ID]
               [--max-cycles MAX_CYCLES] [--event EVENT_TYPE]

Runs the OODA agent from the command line.

options:
  --user-id USER_ID       User identifier (default: demo_user)
  --session-id SESSION_ID Session identifier (default: demo_session)
  --max-cycles MAX_CYCLES Cycles before stopping (default: 1)
  --event EVENT_TYPE      Event type: wrong, correct, code, page, video
```

**How it works:**
1. Calls `create_initial_state()` with provided parameters
2. Adds a mock event to `raw_events` based on `--event` flag
3. Runs `agent.ainvoke(state)`
4. Prints results in color-coded format

**Example output:**
```
$ python demo.py --event wrong --max-cycles 2

═══ OODA CYCLE 1 ═══
OBSERVE: 1 events, type=wrong
ORIENT: Diagnosed struggle with inverse_kinematics
DECIDE: Selected hint intervention (explore)
ACT: Hint delivered via websocket

═══ OODA CYCLE 2 ═══
OBSERVE: 0 events (draining)
ORIENT: No new struggles, monitoring engagement
DECIDE: No intervention needed
ACT: Skipped

Done. 2 cycles completed.
```

### web_demo.py — Server-Side Rendered Demo

**How it works:**
1. GET `/` → runs `agent.ainvoke()` with hardcoded demo data
2. Renders the full OODA state as an HTML page
3. No JavaScript, no forms — a "one-shot" demo

**Use case:** Quick visual check that the agent runs and produces meaningful output. Open `http://127.0.0.1:8000` to see results immediately.

### interactive_demo.py — Form-Based Interactive Demo

**How it works:**
1. GET `/` → Shows HTML form with event type buttons (correct, wrong, code, page, video) and Run/RESET buttons
2. POST `/run` → Accepts selected event type, appends to session event list, runs `agent.ainvoke()`, returns updated state rendered as HTML
3. POST `/reset` → Clears session state, returns fresh form
4. Session state maintained in-memory (dict keyed by UUID)

**Use case:** Live demo where the presenter clicks buttons to simulate student events and shows the agent's response evolving cycle by cycle.

### How Demos Connect

```
demo.py (CLI)
  → direct agent.ainvoke()
  → for developers

web_demo.py (HTTP, no interaction)
  → GET / → agent.ainvoke() → rendered HTML
  → for quick verification

interactive_demo.py (HTTP, interactive)
  → GET / → form
  → POST /run → agent.ainvoke() → updated HTML
  → POST /reset → clear state
  → for live presentation
```

---

## Task 9.3: Fixed Issues

### Infinite Loop (Fixed)

**Root cause:** The original `compile_ooda_agent()` had:
```python
builder.add_conditional_edges("observe", decide_router, ...)
```
But `decide_router` only returned `"act"` or `"pause"`, never `"end"`. The cycle `observe → orient → decide → act → observe → ...` ran forever.

**Fix:** Added `continue_router` that checks `cycle_count >= max_cycles`:
```python
def continue_router(state: OODAState) -> str:
    if state.get("cycle_count", 0) >= state.get("max_cycles", 9999):
        return "end"
    return "orient"
```

And wired it:
```python
builder.add_conditional_edges("observe", continue_router, {"orient": "orient", "end": END})
```

**Verification:** `test_one_ooda_cycle()` passes within 60 seconds instead of hanging forever.

### web_demo.py Button (Fixed)

**Original:** JS `onclick` button that called `/run` — but the function wasn't being invoked. The button just sat there.

**Fix:** Replaced with server-side rendering — the `/` endpoint runs the OODA cycle and renders results directly in HTML. No JavaScript needed.

### `max_cycles` Default (Added)

**Original:** `create_initial_state()` had no `max_cycles` parameter.

**Fix:** Added `max_cycles: int = 9999` to `create_initial_state()` and `max_cycles: int = 9999` to `OODAState`.

---

## PoC Presentation Ideas

### Flow Visualization

Show the OODA loop as a physical dashboard:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  OBSERVE    │────►│  ORIENT     │────►│  DECIDE     │────►│  ACT        │
│             │     │             │     │             │     │             │
│ 2 events    │     │ struggling  │     │ hint (60%)  │     │ "Try using  │
│ 1 correct   │     │ with IK     │     │ practice    │     │ the cosine  │
│ 1 wrong     │     │ engage: 0.7 │     │ (30%)       │     │ law..."     │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       ▲                                                          │
       └──────────────────────────────────────────────────────────┘
```

Each box updates in real-time as cycles progress. The `interactive_demo.py` achieves this by rendering the full state after each POST.

### Bandit Learning Curve

Show a chart where the system starts randomly and converges to the best intervention:

```
Success Rate
  1.0 ┤                                        ╔═══╤═══╤═══╗
  0.8 ┤                               ╔═══╤═══╗║ P │ P │ P ║
  0.6 ┤                    ╔═══╤═══╤══╣ P │ P ║║   │   │   ║
  0.4 ┤          ╔═══╤═══╤╣ H ║ H ║  ║   │   ║║   │   │   ║
  0.2 ┤ ╔═══╤═══╣ H ║   ║║   ║   ║  ║   │   ║║   │   │   ║
  0.0 ┤─╚═══╧═══╩═══╧═══╩╧═══╧═══╧══╧═══╧═══╧╧═══╧═══╧═══╝
      └────────────────────────────────────────────► Cycles
        1   2   3   4   5   6   7   8   9   10  11  12  13
        H=Hint  V=Video  P=Practice (shaded = chosen)
```

System selects Hint initially (random), explores Video once (fails), then converges to Practice as the best arm.
