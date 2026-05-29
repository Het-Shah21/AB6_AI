# Phase 7 — Intervention Engine

## System Design Reference

Master System Design, "Intervention Engine" section. Specified a 3-step pipeline: **Selector** (retrieves candidate interventions), **Generator** (produces personalized content via LLM), and **Delivery** (chooses channel and sends). Design also included an **Effectiveness Tracker** for the multi-armed bandit feedback loop.

---

## Task 7.1: Selector (`src/intervention/selector.py`)

### Purpose

Retrieves candidate interventions for a given set of diagnosed struggles, ordered by expected effectiveness. Acts as the "menu" for the DECIDE node's Thompson Sampling.

### Key Method

```python
class InterventionSelector:
    async def select(
        self,
        struggles: list[str],
        profile: dict,
        engagement: float,
    ) -> list[dict]:
        """
        Returns candidate interventions sorted by expected effectiveness.
        Each candidate: {intervention_id, type, concept, rationale,
                         success_count, trial_count, difficulty, expected_effectiveness}
        """
```

**Selection logic:**

1. **Type matching** based on learning style:
   - Visual/reading → `video_recommendation`
   - Hands-on → `hint` + `practice`
   - Reflective → `code_review`

2. **Difficulty calibration** based on engagement:
   - Engagement < 0.3 → `encouragement` (re-engage before challenging)
   - Mastery 0.3-0.6 → `hint` (gentle guidance)
   - Mastery 0.6-0.8 → `practice` (active learning)
   - Mastery > 0.8 → `code_review` (advanced feedback)

3. **Community boost** from GlobalWisdomStore:
   - If a specific intervention type has high success rate for this concept in the global store, it gets a 1.5× weight multiplier on `expected_effectiveness`.

4. **History de-duplication:**
   - Recent interventions (last 5) of the same type for the same concept are excluded to avoid repetition.

### How It Connects

```
DECIDE → InterventionSelector.select(struggles, profile, engagement)
    → returns candidates with Beta distribution parameters
    → Thompson Sampling chooses one
```

---

## Task 7.2: Generator (`src/intervention/generator.py`)

### Purpose

Generates the actual intervention content using the LLM. Takes a type + concept + profile and produces the intervention text (hint text, video recommendation, code review, etc.).

### Key Method

```python
class InterventionGenerator:
    def __init__(self):
        self.llm = get_llm_for_purpose("reasoning")
    
    async def generate(
        self,
        intervention_type: str,
        concept: str,
        profile: dict,
        struggles: list[str],
        extra_context: str = "",
    ) -> str:
        prompt = ACT_PROMPT_TEMPLATE.format(
            intervention_type=intervention_type,
            concept=concept,
            profile=json.dumps(profile, indent=2),
            struggles=", ".join(struggles),
            extra_context=extra_context,
        )
        response = await self.llm.ainvoke([
            {"role": "system", "content": ACT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])
        return response.content
```

**Design note:** `InterventionGenerator` is called from `InterventionDelivery`, not directly from the DECIDE node. The DECIDE node passes the raw intervention metadata; the delivery layer adds the generated content.

### How It Connects

```
Delivery.prepare() → Generator.generate(type, concept, profile)
    → returns personalized text → packaged into delivery payload
```

---

## Task 7.3: Effectiveness Tracker (`src/intervention/effectiveness.py`)

### Purpose

Tracks the success/failure of each intervention arm, maintaining Beta distribution parameters (α, β) for Thompson Sampling. Persisted to PostgreSQL.

### Key Data Model

```python
class InterventionArm(BaseModel):
    intervention_id: str
    type: str
    concept_id: str
    success_count: int = 0
    trial_count: int = 0
    last_used: str = ""
```

Stored in `ab6_learning_data.ai_intervention_arms` (ORM model `InterventionArmORM`).

### Key Methods

```python
class EffectivenessTracker:
    async def record_result(
        self,
        intervention_id: str,
        was_successful: bool,
    ):
        """Update the arm's Beta parameters."""
        arm = await self.repo.get(intervention_id)
        if not arm:
            logger.warning("Unknown intervention arm: %s", intervention_id)
            return
        
        if was_successful:
            arm.success_count += 1
        arm.trial_count += 1
        arm.last_used = datetime.utcnow().isoformat()
        await self.repo.update(arm)
    
    def get_beta_parameters(self, arm: InterventionArm) -> tuple[int, int]:
        """Return (alpha, beta) for Thompson sampling.
        Uses Beta(1,1) uniform prior."""
        alpha = arm.success_count + 1
        beta_val = arm.trial_count - arm.success_count + 1
        return alpha, beta_val
```

**The Beta prior of (1,1):** This is the uniform distribution on [0,1], meaning the system starts with no bias. After 1 success in 1 trial, the posterior is Beta(2, 1) — slightly confident it's good. After 10 successes in 10 trials, Beta(11, 1) — very confident.

### How It Connects

```
ACT delivers intervention → student responds (success/fail)
    → EffectivenessTracker.record_result(intervention_id, was_successful)
    → PostgreSQL updated
    → Next DECIDE cycle reads updated Beta parameters
    → Thompson Sampling adapts
```

---

## Task 7.4: Delivery (`src/intervention/delivery.py`)

### Purpose

Packages the intervention for delivery and chooses the correct channel. Coordinates between Generator, websocket manager, and SSE manager.

### Key Method

```python
class InterventionDelivery:
    def __init__(self):
        self.generator = InterventionGenerator()
    
    async def prepare_and_deliver(
        self,
        intervention_type: str,
        concept: str,
        profile: dict,
        struggles: list[str],
        channel: str,
        extra_context: str = "",
    ) -> dict:
        content = await self.generator.generate(
            intervention_type, concept, profile, struggles, extra_context
        )
        payload = {
            "type": intervention_type,
            "concept_id": concept,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        if channel == "websocket":
            await ws_manager.send(user_id, payload)
        elif channel == "sse":
            await sse_manager.send(user_id, payload)
        
        return payload
```

**Channel dispatch:**
- `"websocket"` — Real-time push via WebSocket (production choice)
- `"sse"` — Server-Sent Events (alternative for environments with restrictive firewalls)
- `"none"` — Log only (exploration mode)

### How It Connects

```
ACT node → Delivery.prepare_and_deliver(type, concept, profile, ..., channel)
    → Generator.generate() → content
    → ws_manager.send() or sse_manager.send() → student receives intervention
    → returns payload → stored in state.intervention_delivered
```

---

## 4 Components Summary

```
InterventionSelector
    │ select(struggles, profile, engagement)
    ▼
List of candidates with Beta parameters
    │
    ▼ Thompson Sampling (in DECIDE)
    │
    ▼
InterventionDelivery
    │ prepare_and_deliver(type, concept, profile, channel)
    │   └─→ InterventionGenerator.generate() → content
    ▼
Payload sent via WebSocket/SSE
    │
    ▼ Student responds
    │
    ▼
EffectivenessTracker
    │ record_result(intervention_id, was_successful)
    ▼
PostgreSQL → next cycle
```

### PoC Presentation Idea

Show the **Explore vs Exploit** tradeoff:

| Trial | Arm A (hint) | Arm B (practice) | Arm C (video) | Choice | Rationale |
|---|---|---|---|---|---|
| 1 | β(1,1) → 0.72 | β(1,1) → 0.31 | β(1,1) → 0.55 | A | Random (all equal prior) |
| 5 | β(3,2) → 0.68 | β(2,2) → 0.45 | β(1,4) → 0.12 | A | Hint is winning |
| 10 | β(6,4) → 0.61 | β(4,2) → 0.73 | β(1,9) → 0.08 | B | Practice now better |

After 10 trials, the system discovers that practice interventions are actually more effective for this concept, even though the initial hint arm was selected first. Thompson Sampling automatically handles this **exploration-to-exploitation** transition.
