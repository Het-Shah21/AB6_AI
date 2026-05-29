# Phase 5 — OODA Agent Core: Nodes

## Task 5.3: OBSERVE Node (`src/agent/nodes/observe.py`)

### Purpose

Reads raw events from state, enriches them with telemetry and interaction signals, and produces a concise observation summary for ORIENT. It is the input gateway of the OODA loop.

### Key Flow

```python
async def observe_node(state: OODAState) -> dict:
    raw_events = state.get("raw_events", [])
    telemetry = state.get("telemetry_window", {})
    
    # Last event (fast-path for single-event trigger)
    last_event = raw_events[-1] if raw_events else {}
    
    # Compute derived signals
    error_rate = ...  # ratio of wrong/total in window
    interaction_count = len(raw_events)
    time_since_last = ...  # seconds since last event
    
    # Summarize for LLM
    observation_summary = build_observation_prompt(
        event_type=last_event.get("event_type"),
        challenge_id=last_event.get("challenge_id"),
        score=last_event.get("score"),
        error_rate=error_rate,
        interaction_count=interaction_count,
        engagement=telemetry.get("30s", {}).get("engagement", 0.5),
    )
    
    return {
        "raw_events": [],  # Clear processed events
        "observation_summary": observation_summary,
        "telemetry_window": telemetry,
        # _derived_signals are computed but not persisted in state
    }
```

**Key design pattern:** `raw_events` is cleared after processing ("drain the queue"). This prevents redundant re-processing of the same events on subsequent loops. The summary is what flows forward.

### How It Connects

```
state.raw_events (from event pipeline) → OBSERVE → state.observation_summary → ORIENT
```

---

## Task 5.4: ORIENT Node (`src/agent/nodes/orient.py`)

### Purpose

The analytical core. Takes the observation, the learner profile, and concept state, then produces a diagnosis: what the learner is struggling with, why, and how engaged they are. Uses an LLM call with a structured prompt.

### Key Flow

```python
async def orient_node(state: OODAState) -> dict:
    llm = get_llm_for_purpose("reasoning")
    profile = state.get("learner_profile", {})
    concept_state = state.get("concept_state", {})
    summary = state.get("observation_summary", "")
    
    prompt = ORIENT_PROMPT.format(
        profile=json.dumps(profile, indent=2),
        concept_state=json.dumps(concept_state, indent=2),
        observation=summary,
    )
    
    response = await llm.ainvoke([
        {"role": "system", "content": ORIENT_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
        *state.get("messages", []),  # Pass conversation history
    ])
    
    diagnosis = parse_orient_response(response.content)
    
    return {
        "diagnosed_struggles": diagnosis.get("struggles", []),
        "engagement_score": diagnosis.get("engagement_score", 0.5),
        "learner_profile": merge_profile(profile, diagnosis.get("profile_delta", {})),
        "concept_state": update_concept_state(concept_state, diagnosis),
        "messages": [AIMessage(content=diagnosis.get("narrative", ""))],
    }
```

**The LLM call pattern:**
1. Format system prompt (fixed role definition)
2. Format user prompt (dynamic — observation + current state)
3. Append conversation history (messages) for context
4. Parse structured JSON from response
5. Extract `struggles`, `engagement_score`, `profile_delta`, `narrative`

### How It Connects

```
state.observation_summary → ORIENT → state.diagnosed_struggles → DECIDE
                                    state.learner_profile (updated) → next cycle
                                    state.concept_state (updated) → next cycle
```

---

## Task 5.5: DECIDE Node (`src/agent/nodes/decide.py`)

### Purpose

Chooses an intervention using a multi-armed bandit (Thompson Sampling). It retrieves candidate interventions, samples from their Beta distributions, selects the best candidate, and determines whether this is exploration or exploitation.

### Key Flow

```python
async def decide_node(state: OODAState) -> dict:
    struggles = state.get("diagnosed_struggles", [])
    profile = state.get("learner_profile", {})
    engagement = state.get("engagement_score", 0.5)
    
    if not struggles:
        return {"selected_intervention": None, "exploration_flag": False}
    
    # Retrieve candidate interventions from selector (Phase 7)
    candidates = await intervention_selector.select(struggles, profile, engagement)
    
    # Thompson Sampling
    best_arm = None
    best_sample = -float("inf")
    for arm in candidates:
        alpha = arm.get("success_count", 1)
        beta_val = arm.get("trial_count", 2) - alpha + 1  # +1 for prior
        sample = np.random.beta(alpha, beta_val)
        arm["thompson_sample"] = float(sample)
        if sample > best_sample:
            best_sample = sample
            best_arm = arm
    
    # Exploration detection
    exploration = (best_arm.get("trial_count", 0) < 10)
    
    return {
        "selected_intervention": best_arm,
        "intervention_candidates": candidates,
        "exploration_flag": exploration,
        "messages": [
            AIMessage(content=json.dumps({
                "action": "explore" if exploration else "exploit",
                "intervention": best_arm.get("intervention_id") if best_arm else None,
                "rationale": best_arm.get("rationale", "") if best_arm else "",
            }))
        ],
    }
```

**Thompson Sampling intuition:**
- Each arm has a Beta(α, β) posterior, where α = success_count + 1, β = failure_count + 1 (Beta(1,1) is uniform prior)
- `np.random.beta(α, β)` draws a sample from each arm's posterior
- The arm with the highest sample is selected
- Over time, the posterior concentrates around the true success rate

**Effectiveness is tracked in Phase 7's `EffectivenessTracker`.**

### Conditional Router: `decide_router`

```python
def decide_router(state: OODAState) -> str:
    if state.get("should_pause", False):
        return "pause"
    return "act"
```

If PAUSE set `should_pause` in a previous cycle, skip directly to PAUSE to enforce cooldown.

### How It Connects

```
state.diagnosed_struggles → DECIDE → state.selected_intervention → ACT
       ↓                                        ↓
InterventionSelector              state.exploration_flag → transparency logging
(Phase 7)
```

---

## Task 5.6: ACT Node (`src/agent/nodes/act.py`)

### Purpose

Delivers the chosen intervention to the student. It generates the final intervention message via LLM, chooses a delivery channel, increments the cycle counter, and logs to the effectiveness tracker.

### Key Flow

```python
async def act_node(state: OODAState) -> dict:
    intervention = state.get("selected_intervention")
    profile = state.get("learner_profile", {})
    struggles = state.get("diagnosed_struggles", [])
    exploration = state.get("exploration_flag", False)
    
    channel = "websocket" if not exploration else "none"
    
    delivery_payload = {}
    if intervention:
        llm = get_llm_for_purpose("reasoning")
        prompt = ACT_PROMPT.format(
            intervention_type=intervention.get("type"),
            concept=intervention.get("concept", struggles[0] if struggles else ""),
            profile=json.dumps(profile, indent=2),
        )
        response = await llm.ainvoke([
            {"role": "system", "content": ACT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])
        delivery_payload = {
            "type": intervention.get("type"),
            "concept_id": intervention.get("concept"),
            "content": response.content,
            "rationale": intervention.get("rationale", ""),
            "channel": channel,
        }
    
    new_count = state.get("cycle_count", 0) + 1
    return {
        "intervention_delivered": delivery_payload,
        "delivery_channel": channel,
        "cycle_count": new_count,
        "last_cycle_timestamp": datetime.utcnow().isoformat(),
        "messages": [
            AIMessage(content=json.dumps(delivery_payload)),
        ],
    }
```

**Channel selection logic:** Exploration arms (trial_count < 10) use `"none"` channel — the intervention is logged but not delivered to the student. This is the **safe exploration** pattern: new intervention types are tested silently before surfacing.

### How It Connects

```
state.selected_intervention → ACT → state.intervention_delivered → frontend
                                   state.cycle_count++ → next OBSERVE check
                                   state.delivery_channel → delivery router
```

---

## Task 5.7: PAUSE Node (`src/agent/nodes/pause.py`)

### Purpose

Implements a cooldown mechanism. If the last intervention was delivered recently (within the cooldown window), the agent pauses (skips ORIENT→DECIDE→ACT) and loops back to OBSERVE without taking action.

### Key Flow

```python
async def pause_node(state: OODAState) -> dict:
    last_ts = state.get("last_cycle_timestamp")
    if not last_ts:
        return {"should_pause": False}
    
    last_time = datetime.fromisoformat(last_ts)
    elapsed = (datetime.utcnow() - last_time).total_seconds()
    cooldown = 30  # seconds
    
    if elapsed < cooldown:
        logger.info("Cooldown active: %.1fs < %ds", elapsed, cooldown)
        return {"should_pause": True}
    
    return {"should_pause": False}
```

**Cooldown purpose:** Prevents flooding the student with interventions when events arrive rapidly. A remediation video, then 10 seconds later a hint, then 5 seconds later a code review — that's overwhelming. The cooldown forces a minimum gap between interventions.

If `should_pause=True`, the `decide_router` routes to PAUSE instead of ACT, and PAUSE sets `should_pause` back to False on the next cycle (after checking again).

### How It Connects

```
decide_router("pause") → PAUSE → state.should_pause = True → back to OBSERVE
                                                              → next DECIDE → PAUSE again
                                                              → eventually cooldown expires
                                                              → should_pause = False → ACT
```

---

## 5 Nodes Summary Diagram

```
                    ┌─────────────────────────────────────────────┐
                    │                                             ▼
  START ──► OBSERVE ──► continue_router ──► ORIENT ──► DECIDE ──► ACT
                     │      │                           │          │
                     │      └──► END (max_cycles)       │          │
                     │         end                      │ cnt++    │
                     │                                  │          │
                     │                          decide_router      │
                     │                            │    │           │
                     │                   should_pause  │           │
                     │                            │    │           │
                     │                            ▼    ▼           │
                     │                          PAUSE ─────────────┘
                     └──────────────────────────────────────────────┘
```
