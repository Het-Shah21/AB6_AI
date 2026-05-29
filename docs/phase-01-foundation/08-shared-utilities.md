# Task 1.8 — Shared Utilities: exceptions, events, telemetry_math

---

## File: `src/shared/exceptions.py`

### Purpose

Defines a custom exception hierarchy for the entire application. Every module raises its own exception type, allowing API middleware to catch and map them to appropriate HTTP responses.

### Line-by-Line

```python
class AB6AIError(Exception):
    pass
```

**Base exception** for all AB6 AI Agent errors. By catching `AB6AIError`, middleware can distinguish "expected application errors" from "unexpected system errors" (like `KeyError`, `ConnectionError`).

```python
class LLMError(AB6AIError): pass
class LLMFallbackExhaustedError(LLMError): pass
class SanitizationError(AB6AIError): pass
class ConceptGraphError(AB6AIError): pass
class InterventionError(AB6AIError): pass
class AgentError(AB6AIError): pass
class MemoryError(AB6AIError): pass
class IngestionError(AB6AIError): pass
class ChallengeGenerationError(AB6AIError): pass
```

8 subclasses, one per architectural domain:
- **LLMError** — Raised when all LLM providers fail (`LLMFallbackExhaustedError` is the most specific case — all 3 providers exhausted)
- **SanitizationError** — Raised when PII sanitization detects malformed data
- **ConceptGraphError** — Raised on concept extraction failure, bad embeddings
- **InterventionError** — Raised on delivery failure, bad intervention templates
- **AgentError** — Raised on invalid state transitions, missing required fields
- **MemoryError** — Raised on cache misses, memory service failures
- **IngestionError** — Raised on Redis stream write failures
- **ChallengeGenerationError** — Raised when LLM fails to generate a valid challenge after retries

### How It Connects

FastAPI middleware could catch `AB6AIError` to return structured error responses:

```python
@app.exception_handler(AB6AIError)
async def ab6_error_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"error": exc.__class__.__name__, "detail": str(exc)}
    )
```

---

## File: `src/shared/events.py`

### Purpose

Pydantic models for the internal event bus. These are used to type-check events as they flow through the system — from ingestion to the OODA loop.

### Line-by-Line

```python
from pydantic import BaseModel
from typing import Any, Literal
from datetime import datetime
```

```python
class ObservationEvent(BaseModel):
    user_id: str
    session_id: str
    event_type: Literal["start_attempt", "end_attempt", "run_code", "page_view", "video_play", "video_pause", "video_seek"]
    challenge_id: str | None = None
    page: str | None = None
    score: float | None = None
    is_correct: bool | None = None
    metadata: dict[str, Any] = {}
    timestamp: datetime = None
```

**Observation events** represent student actions. The `event_type` is a `Literal` — only these 7 types are valid. Other fields are optional depending on event type:
- `end_attempt` has `score` and `is_correct`
- `page_view` has `page`
- `video_*` events could have `metadata` with playhead position

```python
class TelemetryEvent(BaseModel):
    user_id: str
    session_id: str
    joint_angles: list[float] | None = None
    smoothness: float | None = None
    jerk: float | None = None
    engagement_score: float | None = None
    fps: float | None = None
    timestamp: datetime = None
```

**Telemetry events** carry real-time sensor data. Used by `TelemetryAggregator` to compute derived signals. Most fields are optional since different telemetry sources provide different data.

```python
class DomainEvent(BaseModel):
    event_type: str
    payload: dict[str, Any]
    timestamp: datetime = None
```

**Domain events** are generic typed payloads. Uses a string `event_type` (not Literal) because domain event types are dynamic and defined by the platform.

```python
class InterventionEvent(BaseModel):
    user_id: str
    intervention_id: str
    type: str
    content: dict[str, Any]
    delivered_at: datetime = None
```

**Intervention events** fire when an intervention is delivered. These are used internally by the delivery pipeline and could also be pushed to Redis for external consumers.

### How It Connects

```
POST /api/v1/ai/events → validates with ObservationEvent
    → RedisStreamConsumer.push("ai:observations", event)
    → ARQ Worker deserializes → TelemetryAggregator
    → OODA sees aggregated data in state["raw_events"]
```

---

## File: `src/shared/telemetry_math.py`

### Purpose

Pure numerical functions for computing educational telemetry metrics. No side effects, no I/O — pure math that can be unit tested independently.

### Line-by-Line

```python
import numpy as np
```

NumPy is used for array operations (vectorized computations are faster than Python loops for large datasets).

```python
def jerk(position: list[float], timestamps: list[float]) -> float:
    """
    Compute the average jerk (3rd derivative of position) from a time series.
    Jerk measures how smoothly a student performs a physical task.
    Lower jerk = smoother motion = better motor control.
    """
    if len(position) < 4:
        return 0.0
    pos = np.array(position)
    t = np.array(timestamps)
    dt = np.diff(t)
    vel = np.diff(pos) / dt
    acc = np.diff(vel) / dt[:-1]
    jrk = np.diff(acc) / dt[:-2]
    return float(np.mean(np.abs(jrk)))
```

**Jerk** is the third derivative of position (rate of change of acceleration). In robotics education, smooth motion (low jerk) indicates good understanding of kinematics. Computed with NumPy's `diff` for numerical differentiation:

1. `np.diff(pos)` → velocity (first derivative)
2. `np.diff(vel)` → acceleration (second derivative)  
3. `np.diff(acc)` → jerk (third derivative)
4. `np.mean(np.abs(jrk))` → average absolute jerk

```python
def smoothness(position: list[float], timestamps: list[float]) -> float:
    """
    Compute smoothness as negative log jerk.
    Higher value = smoother motion.
    """
    j = jerk(position, timestamps)
    if j <= 0:
        return 1.0
    return -np.log(j)
```

**Smoothness** transforms jerk into a more interpretable metric. Log transform compresses the wide range of jerk values. Higher smoothness = better.

```python
def angular_velocity(angles: list[float], timestamps: list[float]) -> float:
    """
    Compute average absolute angular velocity from joint angle data.
    """
    if len(angles) < 2:
        return 0.0
    ang = np.array(angles)
    t = np.array(timestamps)
    dt = np.diff(t)
    omega = np.diff(ang) / dt
    return float(np.mean(np.abs(omega)))
```

Average angular velocity. Used by the Aggregator to detect hesitation or rapid movements.

```python
def engagement_score_telemetry(
    error_rate: float,
    smoothness_val: float,
    attempt_velocity: float,
    w_error: float = 0.4,
    w_smoothness: float = 0.3,
    w_velocity: float = 0.3,
) -> float:
    """
    Compute engagement score as weighted combination of telemetry signals.
    """
    score = (
        w_error * (1.0 - error_rate) +
        w_smoothness * smoothness_val +
        w_velocity * attempt_velocity
    )
    return float(np.clip(score, 0.0, 1.0))
```

**Engagement score** is a weighted combination:
- Low error rate → higher engagement (weight 0.4)
- Smooth motion → higher engagement (weight 0.3)
- High attempt velocity → higher engagement (weight 0.3)
- Final score clipped to [0, 1]

### How It Connects

```
TelemetryAggregator.aggregate()
    → calls telemetry_math.smoothness() and telemetry_math.angular_velocity()
    → stores in telemetry_window["2m"]["smoothness"]
OBSERVE node reads telemetry_window
    → passes _derived_signals to ORIENT
ORIENT computes engagement_score from signals and mastery
```

### PoC Presentation Idea

Show the math with sample data:

```python
from src.shared.telemetry_math import smoothness, engagement_score_telemetry

positions = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]
times = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]  # seconds
print(f"Smoothness: {smoothness(positions, times):.2f}")

# A struggling student: high error rate, jerky motion
engagement = engagement_score_telemetry(
    error_rate=0.7, smoothness_val=0.3, attempt_velocity=0.2
)
print(f"Engagement (struggling): {engagement:.2f}")  # ~0.33
```

---

## File: `src/db/engine.py` (already covered in Task 1.5)
## File: `src/db/models/__init__.py`

Simply re-exports all 7 model classes:

```python
from src.db.models.ai_learner_profile import AILearnerProfile
from src.db.models.ai_intervention_log import AIInterventionLog
from src.db.models.ai_wisdom_store import AIWisdomStore
from src.db.models.ai_concept import AIConcept
from src.db.models.ai_concept_edge import AIConceptEdge
from src.db.models.ai_concept_mapping import AIConceptMapping
from src.db.models.ai_population_benchmark import AIPopulationBenchmark
```

## File: `src/db/repositories/__init__.py`

Similarly re-exports all 5 repository classes.

## File: `docker-compose.yml`

Defines 3 services:

```yaml
version: "3.9"
services:
  postgres:
    image: pgvector/pgvector:pg18
    environment:
      POSTGRES_DB: ab6_ai
      POSTGRES_USER: ab6
      POSTGRES_PASSWORD: ab6_pass
    ports: ["5432:5432"]
    volumes: ["postgres_data:/var/lib/postgresql/data"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  api:
    build: .
    env_file: .env
    ports: ["8000:8000"]
    depends_on: [postgres, redis]
    command: uvicorn src.api.app:app --host 0.0.0.0 --port 8000

volumes:
  postgres_data:
```

- `pgvector/pgvector:pg18` — PostgreSQL 18 with pgvector pre-installed
- `redis:7-alpine` — Lightweight Redis (7MB image)
- `api` — Builds from local Dockerfile, depends on postgres+redis

Not used in local demo (no Docker), but ready for production deployment.
