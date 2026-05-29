# Phase 6 — Dual Memory

## System Design Reference

Master System Design, "Dual Memory Systems" section. Specified a personal store (per-user session cache + DB-backed profile) and a global wisdom store (aggregated peer analytics + concept archetypes).

---

## Task 6.1: Personal Wisdom (`src/memory/personal.py`)

### Purpose

Manages the per-learner session state in Redis and the long-term persistent profile in PostgreSQL. This is the **short-term + long-term memory** for each student.

### Key Components

**SessionCache** (Redis-backed, TTL = 30 minutes):
```python
class SessionCache:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis
    
    async def get_state(self, session_id: str) -> dict | None:
        data = await self.redis.get(f"session:{session_id}")
        return json.loads(data) if data else None
    
    async def set_state(self, session_id: str, state: dict, ttl: int = 1800):
        await self.redis.setex(f"session:{session_id}", ttl, json.dumps(state))
    
    async def clear_state(self, session_id: str):
        await self.redis.delete(f"session:{session_id}")
```

**Purpose:** The `SessionCache` stores the OODA state in Redis with a 30-minute TTL. This is the **session memory** — if the student leaves and returns within 30 minutes, their state is restored. After 30 minutes, the state is garbage-collected by Redis.

**ProfileStore** (PostgreSQL-backed, persistent):
```python
class ProfileStore:
    def __init__(self, session_factory):
        self.session_factory = session_factory
    
    async def load_profile(self, user_id: str) -> LearnerProfile | None:
        async with self.session_factory() as session:
            repo = ProfileRepo(session)
            profile = await repo.get_by_user_id(user_id)
            if profile:
                return LearnerProfile.model_validate(profile.__dict__)
        return None
    
    async def save_profile(self, profile: LearnerProfile):
        async with self.session_factory() as session:
            repo = ProfileRepo(session)
            await repo.upsert(profile.model_dump())
            await session.commit()
```

**Purpose:** The `ProfileStore` persists the `LearnerProfile` to PostgreSQL. Unlike the session cache (which is disposable), the profile store survives restarts. The `upsert` is important — it either inserts a new profile or updates an existing one based on `user_id`.

### How It Connects

```
OODA cycle start → SessionCache.get_state(session_id)
    → if found: restore full state → resume loop
    → if not found: ProfileStore.load_profile(user_id) → ORIENT initializes from stored profile
OODA cycle end → SessionCache.set_state(session_id, state)
    → ProfileStore.save_profile(learner_profile) (debounced — saved every N cycles)
```

---

## Task 6.2: Global Wisdom (`src/memory/global_wisdom.py`)

### Purpose

Aggregated peer analytics — the "wisdom of the crowd" for each concept. Stores common mistake patterns, average time to mastery, and effective intervention types, derived from all learners' data.

### Key Data Structure

```python
class GlobalWisdom(BaseModel):
    concept_id: str
    average_mastery_time_hours: float = 0.0
    common_mistakes: list[str] = []
    effective_interventions: list[dict] = []  # [{type, success_rate}]
    peer_count: int = 0
    updated_at: str = ""
```

Stored in PostgreSQL table `ab6_learning_data.ai_global_wisdom`. Updated by a background cron job or manually triggered after enough new data accumulates.

### Key Methods

```python
class GlobalWisdomStore:
    async def get_insight(self, concept_id: str) -> GlobalWisdom | None:
        query = text("SELECT * FROM ai_global_wisdom WHERE concept_id = :cid")
        row = await session.execute(query, {"cid": concept_id})
        return GlobalWisdom(**row.mappings().one()) if row else None
    
    async def aggregate(self):
        """Recompute global wisdom from all learner data."""
        profiles = await ProfileRepo.get_all()
        concepts = await ConceptRepo.get_all()
        
        for concept in concepts:
            relevant = [p for p in profiles if concept.concept_id in p.mastery_map]
            if len(relevant) < 3:
                continue  # Not enough data
            
            avg_time = np.mean([
                p.mastery_map[concept.concept_id].get("time_to_mastery_hours", 0)
                for p in relevant if concept.concept_id in p.mastery_map
            ])
            
            # ... compute common mistakes, effective interventions ...
            
            await self.upsert(GlobalWisdom(
                concept_id=concept.concept_id,
                average_mastery_time_hours=float(avg_time),
                common_mistakes=common_mistakes,
                effective_interventions=effective_interventions,
                peer_count=len(relevant),
            ))
```

**Privacy note:** Raw learner data is never exposed. The global wisdom store only contains aggregated statistics (means, counts, lists of anonymized mistake patterns). Individual learner profiles are never mixed.

### How It Connects

```
CommunityInsightTool.get_community_insight(concept_id)
    → GlobalWisdomStore.get_insight(concept_id)
    → returns aggregated peer data
    → ORIENT uses as context for diagnosis
    → DECIDE uses as factor in intervention selection
```

---

## Task 6.3: Session Cache (`src/memory/session_cache.py`)

### Purpose

Alternative or supplementary to Redis-based SessionCache. Provides an in-memory fallback when Redis is unavailable, and batch operations for multi-session management.

### Key Methods

```python
class InMemorySessionCache:
    def __init__(self):
        self._store: dict[str, dict] = {}
    
    async def get(self, session_id: str) -> dict | None:
        return self._store.get(session_id)
    
    async def set(self, session_id: str, data: dict):
        self._store[session_id] = data
    
    async def delete(self, session_id: str):
        self._store.pop(session_id, None)
    
    async def get_active_sessions(self) -> list[str]:
        return list(self._store.keys())
```

This is the **zero-dependency fallback**. When Redis is not configured, the agent uses `InMemorySessionCache` instead. The API is identical to the Redis version, making them swappable via dependency injection.

### How It Connects

```
config.get("redis_url") is None
    → InMemorySessionCache (in-process, lost on restart)
config.get("redis_url") is set
    → SessionCache(redis_client) (persistent across restarts)
```

---

## Task 6.4: Benchmarks (`src/memory/benchmarks.py`)

### Purpose

Performance benchmarks for the dual memory system. Tests read/write latency for Redis and in-memory caches, plus query performance for the global wisdom aggregate function.

### Key Tests

```python
async def benchmark_session_cache(cache, iterations=1000):
    start = time.time()
    for i in range(iterations):
        await cache.set(f"test:{i}", {"data": "x" * 100})
        await cache.get(f"test:{i}")
    elapsed = time.time() - start
    return {"iterations": iterations, "total_seconds": elapsed, "avg_ms": elapsed / iterations * 1000}

async def benchmark_global_wisdom_aggregate(store, concepts=50):
    start = time.time()
    for c in [f"concept:{i}" for i in range(concepts)]:
        await store.aggregate_for_concept(c)
    elapsed = time.time() - start
    return {"concepts": concepts, "total_seconds": elapsed, "avg_per_concept_ms": elapsed / concepts * 1000}
```

**Expected performance:**
| Cache Type | Read (avg) | Write (avg) | Notes |
|---|---|---|---|
| InMemorySessionCache | ~0.02ms | ~0.02ms | Fastest, no I/O |
| Redis SessionCache | ~1ms | ~1ms | Network round trip |
| PostgreSQL ProfileStore | ~5ms | ~15ms | Disk I/O, serialization |
| GlobalWisdom.aggregate | ~50ms/concept | — | Full table scan |

### PoC Presentation Idea

Show the **memory hierarchy** as concentric circles:

```
┌─────────────────────────────────────┐
│  PostgreSQL (persistent profiles)    │  ← days/years
│  ┌─────────────────────────────┐    │
│  │  Redis (30min session)      │    │  ← session
│  │  ┌─────────────────────┐    │    │
│  │  │  In-Memory (current │    │    │  ← request
│  │  │  cycle cache)       │    │    │
│  │  └─────────────────────┘    │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │  Global Wisdom (aggregated) │    │  ← all users
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
```

Demonstrate that recovering a session from Redis takes ~1ms, while rebuilding from PostgreSQL takes ~200ms (includes OODA cold start).
