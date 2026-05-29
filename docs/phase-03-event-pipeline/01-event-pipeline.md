# Phase 3 — Event Pipeline

## System Design Reference

Master System Design, "Event Ingestion" section. The design specified Redis Streams as the event backbone, with typed Pydantic schemas for validation, a consumer for push/read, an aggregator for windowed telemetry, and an ARQ worker for background processing.

---

## Task 3.1: Schemas (`src/ingestion/schemas.py`)

### Purpose

Pydantic models for API request validation and Redis stream event format. Every event entering the system is validated by one of these schemas before being pushed to Redis.

### Key Models

```python
class ObservationRequest(BaseModel):
    event_type: Literal["start_attempt", "end_attempt", "run_code", "page_view", ...]
    challenge_id: str | None = None
    score: float | None = Field(None, ge=0.0, le=1.0)
    is_correct: bool | None = None
    metadata: dict[str, Any] = {}
```

Validated at the API boundary. The `Field(ge=0.0, le=1.0)` constraint ensures scores are in [0, 1]. Invalid requests are rejected with a 422 response before reaching the agent.

```python
class BatchObservationRequest(BaseModel):
    events: list[ObservationRequest]
```

Bulk ingestion — pushes multiple events in a single API call. Used by the frontend to batch events during page transitions.

```python
STREAM_OBSERVATIONS = "ai:observations"
STREAM_TELEMETRY = "ai:telemetry"
STREAM_DOMAIN_EVENTS = "ai:domain_events"
```

Redis stream name constants. Used by both the consumer (writer) and the worker (reader).

---

## Task 3.2: RedisStreamConsumer (`src/ingestion/consumer.py`)

### Purpose

Interface to Redis Streams. Provides `push_event()` to append events and `read_events()` to consume them with consumer groups.

### Key Methods

```python
class RedisStreamConsumer:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def push_event(
        self, stream: str, event: dict[str, Any]
    ) -> str:
        """Append an event to a Redis stream. Returns the stream entry ID."""
        event_id = await self.redis.xadd(stream, event, maxlen=10000)
        return event_id
```

`xadd` appends a dict to the Redis stream. `maxlen=10000` trims the stream to the latest 10K entries, preventing unbounded memory growth.

```python
    async def read_events(
        self, stream: str, group: str, consumer: str,
        count: int = 10, block_ms: int = 2000
    ) -> list[dict]:
        """Read events from a stream using a consumer group."""
        try:
            await self.redis.xgroup_create(stream, group, id="0", mkstream=True)
        except aioredis.ResponseError:
            pass  # Group already exists
        raw = await self.redis.xreadgroup(
            group, consumer, {stream: ">"}, count=count, block=block_ms
        )
        # Parse and return events
```

Uses Redis consumer groups for reliable processing:
1. Creates the consumer group if it doesn't exist (`mkstream=True`)
2. `xreadgroup` with `">"` reads only new (unconsumed) messages
3. Messages are not auto-acknowledged — the ARQ worker must explicitly ack after processing

### How It Connects

```
POST /events → validates with ObservationRequest
    → RedisStreamConsumer.push_event("ai:observations", event)
    → ARQ Worker.read_events() → process
```

---

## Task 3.3: TelemetryAggregator (`src/ingestion/aggregator.py`)

### Purpose

Buffers telemetry events into time windows (30s, 2m, 5m) and computes derived signals (smoothness, engagement) per user. The OBSERVE node calls `aggregate(user_id)` to get the latest windowed telemetry without accessing Redis directly.

### Key Methods

```python
class TelemetryAggregator:
    def __init__(self):
        # In-memory buffer: {user_id: {window: [events]}}
        self._buffers: dict[str, dict[str, list]] = defaultdict(
            lambda: {"30s": [], "2m": [], "5m": []}
        )

    def update(self, user_id: str, telemetry: dict):
        window = self._buffers[user_id]
        now = time.time()
        cutoff_windows = {"30s": 30, "2m": 120, "5m": 300}
        for w, seconds in cutoff_windows.items():
            cutoff = now - seconds
            window[w].append(telemetry)
            window[w] = [e for e in window[w] if e.get("timestamp", now) > cutoff]

    def aggregate(self, user_id: str) -> dict:
        window = self._buffers.get(user_id)
        if not window:
            return {}
        result = {}
        for w, events in window.items():
            if not events:
                continue
            smooth = np.mean([e.get("smoothness", 0.5) for e in events])
            engagement = np.mean([e.get("engagement_score", 0.5) for e in events])
            result[w] = {"smoothness": smooth, "engagement": engagement}
        return result
```

- `_buffers` — Dict of dicts. Each user has 3 windows: 30s (near real-time), 2m (short-term trend), 5m (medium-term trend)
- `update()` — Appends an event and evicts entries outside the window
- `aggregate()` — Returns mean smoothness and engagement per window

**Design note:** This is purely in-memory. In production, the buffer would be stored in Redis with TTL to survive restarts and scale across workers.

### How It Connects

```
WebSocket /telemetry/ws → telemetry_router
    → RedisStreamConsumer.push("ai:telemetry", event)
    → ARQ Worker reads telemetry stream
        → TelemetryAggregator.update(user_id, event)
OBSERVE node calls TelemetryAggregator.aggregate(user_id)
    → gets windowed smoothness, engagement
```

---

## Task 3.4: ARQ Worker (`src/ingestion/worker.py`)

### Purpose

Background task worker using ARQ (Async Redis Queue). Processes events from Redis streams asynchronously, offloading work from the FastAPI request-response cycle.

### Key Functions

```python
async def process_observation(ctx, event: dict):
    redis: aioredis.Redis = ctx["redis"]
    aggregator: TelemetryAggregator = ctx["aggregator"]
    
    # Enrich event with derived fields
    event["enriched_at"] = datetime.utcnow().isoformat()
    
    # Update telemetry aggregator
    if event.get("event_type") in ("video_play", "video_pause", "video_seek"):
        telemetry_event = TelemetryEvent(
            user_id=event["user_id"],
            smoothness=event.get("metadata", {}).get("smoothness"),
        )
        aggregator.update(event["user_id"], telemetry_event.model_dump())
    
    # Store enriched event for OODA consumption
    await redis.lpush(f"user:{event['user_id']}:events", json.dumps(event))
    await redis.ltrim(f"user:{event['user_id']}:events", 0, 99)
```

ARQ worker functions receive a `ctx` dict with Redis client and application state. The pattern:
1. Read from Redis stream
2. Enrich/transform the event
3. Push to a user-specific Redis list (capped at 100)
4. The OODA agent reads from this list when triggered

```python
# Worker settings
class WorkerSettings:
    redis_settings = RedisSettings(host="localhost", port=6379)
    functions = [process_observation, process_telemetry, process_domain_event]
    queue_name = "ab6:arq:queue"
```

ARQ configuration:
- Connects to Redis on localhost:6379
- Registers 3 worker functions
- Uses the `ab6:arq:queue` Redis list as the job queue

### How It Connects

```
ARQ Worker ← polls Redis stream "ai:observations"
    → process_observation()
    → TelemetryAggregator.update()
    → Redis list "user:{id}:events" (for OODA)
    → OODA Observe node reads from raw_events
```

### PoC Presentation Idea

Show the event flow as a **conveyor belt**:

```
Student Event → Redis Stream → ARQ Worker → Aggregator → OODA
   (raw)        (durable)      (async)       (windowed)   (decision)
```

Demonstrate with `redis-cli` monitoring:

```bash
redis-cli MONITOR
# See events flowing: XADD ai:observations * event_type wrong score 0.3
```
