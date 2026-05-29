# Phase 8 — API Layer

## System Design Reference

Master System Design, "API Design" section. Specified a FastAPI application with 5 routers (health, agent, events, telemetry, intervention), dependency injection for shared resources, CORS middleware, and exception handlers.

---

## Task 8.1: Application Factory (`src/api/app.py`)

### Purpose

FastAPI application factory with lifespan management for shared resources (Redis, database session factory, ARQ worker).

### Key Components

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    
    # Initialize Redis
    redis = await aioredis.from_url(settings.redis_url)
    app.state.redis = redis
    
    # Initialize database session factory
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine)
    app.state.session_factory = session_factory
    
    # Initialize OODA graph
    agent = await compile_ooda_agent()
    app.state.agent = agent
    
    # Start ARQ worker (in background)
    worker = arq.ArqRedis(redis_settings=RedisSettings(
        host=settings.redis_host, port=settings.redis_port
    ))
    app.state.worker = worker
    
    yield
    
    # Shutdown
    await redis.close()
    await engine.dispose()
```

**Lifespan pattern:** `@asynccontextmanager` replaces the deprecated `startup`/`shutdown` event handlers. Resources initialized here are available via `request.app.state`.

**Shared state:**
- `app.state.redis` — Redis client used by consumer, cache
- `app.state.session_factory` — For dependency injection in route handlers
- `app.state.agent` — Compiled OODA agent (singleton, compiled once)
- `app.state.worker` — ARQ background worker

### Application Construction

```python
app = FastAPI(title="AB6 AI Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1/health", tags=["Health"])
app.include_router(agent_router, prefix="/api/v1/agent", tags=["Agent"])
app.include_router(events_router, prefix="/api/v1/events", tags=["Events"])
app.include_router(telemetry_router, prefix="/api/v1/telemetry", tags=["Telemetry"])
app.include_router(intervention_router, prefix="/api/v1/interventions", tags=["Interventions"])
```

---

## Task 8.2: Routers

### Health Router (`routers/health.py`)

```python
@router.get("/")
async def health_check(request: Request):
    redis = request.app.state.redis
    try:
        await redis.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {
        "status": "operational",
        "redis": redis_ok,
        "agent_compiled": hasattr(request.app.state, "agent"),
    }
```

**Purpose:** Liveness probe. Returns 200 if the app is running, with component health indicators. Used by Docker health checks and load balancers.

### Agent Router (`routers/agent.py`)

```python
@router.post("/cycle")
async def run_ooda_cycle(request: Request, body: AgentCycleRequest):
    agent = request.app.state.agent
    state = create_initial_state(
        user_id=body.user_id,
        session_id=body.session_id,
        max_cycles=1,
    )
    state["raw_events"] = [e.model_dump() for e in body.events]
    
    result = await agent.ainvoke(state)
    return AgentCycleResponse(
        intervention=result.get("intervention_delivered"),
        cycle_count=result.get("cycle_count", 0),
        struggles=result.get("diagnosed_struggles", []),
        narrative=get_last_ai_message(result),
    )
```

**Purpose:** One-shot OODA cycle. Takes user_id, session_id, and events → runs one OODA cycle → returns intervention if any. This is the core API used by web_demo and interactive_demo.

### Events Router (`routers/events.py`)

```python
@router.post("/ingest")
async def ingest_event(body: ObservationRequest, request: Request):
    consumer = RedisStreamConsumer(request.app.state.redis)
    event_id = await consumer.push_event(STREAM_OBSERVATIONS, body.model_dump())
    return {"event_id": event_id, "status": "queued"}

@router.post("/batch")
async def ingest_batch(body: BatchObservationRequest, request: Request):
    consumer = RedisStreamConsumer(request.app.state.redis)
    ids = []
    for event in body.events:
        event_id = await consumer.push_event(STREAM_OBSERVATIONS, event.model_dump())
        ids.append(event_id)
    return {"event_ids": ids, "count": len(ids)}
```

**Purpose:** Event ingestion endpoint. Each event is validated by `ObservationRequest` and pushed to the Redis stream. The ARQ worker processes them asynchronously.

### Telemetry Router (`routers/telemetry.py`)

```python
@router.websocket("/ws")
async def telemetry_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            # Validate and push to telemetry stream
            consumer.push_event(STREAM_TELEMETRY, data)
    except WebSocketDisconnect:
        pass
```

**Purpose:** WebSocket endpoint for real-time telemetry (video play/pause/seek, mouse movements). Used by the frontend to stream telemetry data without HTTP overhead.

### Intervention Router (`routers/intervention.py`)

```python
@router.get("/history/{user_id}")
async def get_history(user_id: str, request: Request, limit: int = 20):
    repo = InterventionRepo(request.app.state.session_factory)
    return await repo.get_history(user_id, limit)

@router.post("/history/{intervention_id}/feedback")
async def record_feedback(intervention_id: str, body: FeedbackRequest, request: Request):
    tracker = EffectivenessTracker(request.app.state.session_factory)
    await tracker.record_result(intervention_id, body.was_successful)
    return {"status": "recorded"}
```

**Purpose:** Intervention history retrieval and feedback recording. The feedback endpoint feeds the EffectivenessTracker loop.

---

## Task 8.3: Middleware & Exception Handlers

```python
@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start
    logger.info(
        "%s %s → %d (%.2fms)",
        request.method, request.url.path,
        response.status_code, elapsed * 1000,
    )
    return response
```

**Purpose:**
- `ValidationError` handler ensures Pydantic validation errors return a clean 422 JSON response
- `log_requests` middleware provides request-level logging with timing

---

## API Endpoint Summary

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health/` | Liveness + component status |
| POST | `/api/v1/agent/cycle` | One-shot OODA cycle |
| POST | `/api/v1/events/ingest` | Single event ingestion |
| POST | `/api/v1/events/batch` | Batch event ingestion |
| WS | `/api/v1/telemetry/ws` | Real-time telemetry stream |
| GET | `/api/v1/interventions/history/{user_id}` | Intervention history |
| POST | `/api/v1/interventions/history/{id}/feedback` | Record effectiveness |
