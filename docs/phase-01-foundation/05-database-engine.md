# Task 1.5 — Database Engine: `src/db/engine.py`

## System Design Reference

Master System Design, "Data Layer — Database Connection" section. The design specified a lazy-initialized async SQLAlchemy engine with connection pooling, to be shared across all repositories.

## Purpose

Creates and manages the SQLAlchemy **async engine** and **session factory**. This is the single point of database connectivity for the entire application. All 7 ORM models inherit from the `Base` class defined here.

## Line-by-Line Explanation

```python
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
```

Imports SQLAlchemy 2.0's async components:
- `AsyncEngine` — Type hint for the async engine
- `AsyncSession` — Type hint for async database sessions
- `async_sessionmaker` — Factory that creates `AsyncSession` instances with consistent configuration
- `create_async_engine` — Creates the actual database engine from a URL

These are the SQLAlchemy 2.0 async equivalents of `create_engine`, `sessionmaker`, `Session`. The `asyncio` extension enables non-blocking database operations — critical for a server that handles multiple concurrent students.

```python
from sqlalchemy.orm import DeclarativeBase
```

SQLAlchemy 2.0 introduced `DeclarativeBase` as the new base class for ORM models (replacing the old `declarative_base()` function). All 7 ORM models will inherit from this.

```python
from src.config.settings import get_settings
```

Imports the cached singleton settings object to read the `database_url` connection string.

```python
class Base(DeclarativeBase):
    pass
```

**The declarative base.** Every ORM model inherits from `Base`. SQLAlchemy uses this to:
- Map model classes to database tables
- Track all registered models for `CREATE TABLE` and Alembic migrations
- Provide the `metadata` object used by `alembic init`

The class body is empty because all shared configuration is in `DeclarativeBase` itself. No custom metaclass or table-naming convention is needed.

```python
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
```

**Module-level globals** for the singleton engine and session factory. These start as `None` and are initialized on first use (lazy loading).

The `| None` syntax (Python 3.10+) indicates these are optional — they don't exist until `get_engine()` or `get_session_factory()` is called.

**Design decision:** Module-level singletons ensure all parts of the application share the same connection pool. Creating a new engine per request would exhaust database connections and lose connection pooling benefits.

```python
async def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_size=10,
            max_overflow=20,
        )
    return _engine
```

**Lazy engine initializer:**

1. Declares `global _engine` to modify the module-level variable
2. Checks if `_engine is None` — if already created, skips initialization (singleton pattern)
3. Calls `get_settings()` to read `database_url` (which triggers `.env` loading on first call)
4. `create_async_engine(...)` creates the connection pool:
   - `echo=False` — Don't log SQL statements. Set to `True` for debugging.
   - `pool_size=10` — Maintain 10 persistent connections in the pool
   - `max_overflow=20` — Allow up to 20 additional connections during load spikes
   - Total maximum connections: 30 (10 pool + 20 overflow)

**Why pool_size=10?** The FastAPI server runs with multiple workers (default: 1 for uvicorn, but could scale). With 10 connections per worker, 3 workers would use 30 connections — well within PostgreSQL's default `max_connections=100`.

```python
async def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        engine = await get_engine()
        _session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory
```

**Session factory initializer:**

1. Gets the engine (which triggers its own lazy init)
2. Creates `async_sessionmaker` with:
   - `engine` — The engine to bind sessions to
   - `class_=AsyncSession` — Use the standard async session class
   - `expire_on_commit=False` — **Important design choice.** Normally, SQLAlchemy expires all objects after commit, meaning you can't access their attributes without a new query. Setting this to `False` allows accessing committed objects for read-only display (e.g., returning data in API responses).

```python
async def get_session() -> AsyncSession:
    factory = await get_session_factory()
    return factory()
```

**Create a new session.** This is the primary API consumed by repositories. Usage pattern:

```python
async with get_session() as session:
    result = await session.execute(select(Model).where(...))
```

Or in repositories that manage their own session:

```python
session = await get_session()
profile = await self.get(user_id)  # uses session internally
```

```python
async def close_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
```

**Shutdown hook.** Called during application shutdown (see `src/api/app.py` lifespan):
1. Checks if engine exists
2. `await _engine.dispose()` — Closes all pooled connections gracefully. Waits for in-flight queries to complete.
3. Sets `_engine = None` — Allows re-initialization if needed

Without this, connections would leak until the Python process exits (which could take minutes with persistent database connections).

## How It Connects

```
src/db/engine.py
    │
    ├── Base ──→ src/db/models/*.py (7 models inherit from Base)
    │
    ├── get_session() ──→ src/db/repositories/*.py (5 repos use sessions)
    │                         │
    │                         ├── orient.py → LearnerProfileRepo()
    │                         ├── decide.py → WisdomRepo()
    │                         └── act.py → InterventionRepo()
    │
    └── close_engine() ──→ src/api/app.py (lifespan shutdown)

Dependency chain:
    get_settings() → settings.database_url → create_async_engine() → engine
    engine → async_sessionmaker() → AsyncSession
    AsyncSession → Repo CRUD operations
```

## PoC Presentation Idea

Show the lazy initialization by tracing calls:

```python
import asyncio
from src.db.engine import get_engine, get_session

async def demo():
    # No DB connection exists yet
    print("Before: engine is None")  # _engine is None
    
    engine = await get_engine()
    print(f"After: engine={engine}")  # Engine created lazily
    
    session = await get_session()
    result = await session.execute("SELECT 1")
    print(f"Query: {result.scalar()}")  # 1
    
    from src.db.engine import close_engine
    await close_engine()
    print("Engine disposed")
    
asyncio.run(demo())
```

If PostgreSQL is down, the error surfaces at `get_engine()` time (not at import), giving the application a chance to handle it gracefully.
