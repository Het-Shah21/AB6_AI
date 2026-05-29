# Task 1.3 — Configuration System: `src/config/settings.py`

## System Design Reference

Master System Design, "Infrastructure Configuration" section. The design specified:
- Single source of truth for all configuration
- Environment variable overrides with sensible defaults
- `.env` file support for local development
- Cached singleton access pattern

## Purpose

`settings.py` defines the global `Settings` class that every module in the codebase imports to read configuration. It uses `pydantic-settings` to automatically merge values from:
1. Default values in the class definition
2. `.env` file (if present)
3. Actual environment variables (highest priority)

## Line-by-Line Explanation

```python
from pydantic_settings import BaseSettings
```

Imports Pydantic's settings class. `BaseSettings` behaves like `BaseModel` but with automatic env var loading. For every field you define, it looks for a matching environment variable (case-insensitive by default).

```python
from functools import lru_cache
```

Imports the least-recently-used cache decorator. Used on `get_settings()` to ensure only ONE instance of `Settings` is ever created — the singleton pattern.

```python
class Settings(BaseSettings):
```

Defines the settings class. All fields are type-annotated. Pydantic validates types at creation time and raises clear errors if types don't match (e.g., if `llm_rate_limit_rpm` is set to a string).

```python
    database_url: str = "postgresql+asyncpg://ab6:ab6_pass@localhost:5432/ab6_ai"
```

Default PostgreSQL connection string. Format: `dialect+driver://user:password@host:port/database`.
- `postgresql+asyncpg` — SQLAlchemy dialect (`postgresql`) with `asyncpg` async driver
- `ab6:ab6_pass` — default user/password
- `localhost:5432` — default host and PostgreSQL port
- `ab6_ai` — database name

**Overridable** by setting the `DATABASE_URL` environment variable (e.g., in `.env`). In production, this would point to a real PostgreSQL instance.

```python
    redis_url: str = "redis://localhost:6379/0"
```

Default Redis connection string. Format: `redis://host:port/db`.

```python
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
```

API keys default to empty strings. The `llm/provider.py` checks these when initializing LangChain chat models. If they're empty, `init_chat_model()` raises an authentication error, which is caught by the fallback chain.

**Design decision:** Empty strings as defaults means the code gracefully detects "no key configured" rather than raising at import time. The error surfaces at first LLM call, which is caught by try/except in orient/decide nodes.

```python
    llm_primary_provider: str = "openai"
    llm_primary_model: str = "gpt-4o-mini"
    llm_reasoning_model: str = "gpt-4o"
    llm_fallback_1_provider: str = "anthropic"
    llm_fallback_1_model: str = "claude-sonnet-4-20250514"
    llm_fallback_2_provider: str = "google_genai"
    llm_fallback_2_model: str = "gemini-2.5-flash"
    llm_embedding_model: str = "text-embedding-3-small"
```

LLM model routing:
- **Primary** (`gpt-4o-mini`): Used by DECIDE node. Fast, cheap, good for structured JSON output.
- **Reasoning** (`gpt-4o`): Used by ORIENT node. Smarter, better at diagnosis.
- **Fallback 1** (`claude-sonnet-4-20250514`): If OpenAI fails (rate limit, outage), try Anthropic.
- **Fallback 2** (`gemini-2.5-flash`): If both OpenAI and Anthropic fail, try Google.
- **Embedding** (`text-embedding-3-small`): Used by concept graph builder to create embeddings. Separate from chat models because it uses the `OpenAIEmbeddings` class instead of `init_chat_model`.

```python
    llm_rate_limit_rpm: int = 100
```

**Rate limit:** 100 requests per minute per provider. This is shared across all LLM calls. The `RateLimiter` class in `src/llm/rate_limiter.py` enforces this with a sliding window.

```python
    sentry_dsn: str = ""
```

Sentry Data Source Name. If set, `sentry-sdk` initializes and reports exceptions to the Sentry dashboard. Empty by default for local development.

```python
    log_level: str = "INFO"
```

Root logger level. Can be set to `DEBUG` during development, `WARNING` or `ERROR` in production. The demo scripts override this to `ERROR` to suppress verbose DB/LLM failure logs.

```python
    redis_stream_observation: str = "ai:observations"
    redis_stream_telemetry: str = "ai:telemetry"
    redis_stream_domain_events: str = "ai:domain_events"
```

Redis stream names. These are like Kafka topics — event producers write to them and consumers read from them. Three separate streams for different event types:
- `ai:observations` — Student interaction events (quiz attempts, code runs, page views)
- `ai:telemetry` — Real-time telemetry data (joint angles, smoothness)
- `ai:domain_events` — Domain-specific events (course completion, badge earned)

```python
    intervention_cooldown_seconds: int = 60
```

Minimum time between interventions for the same user. The PAUSE node checks this. Prevents "notification fatigue" — if you just showed a hint 30 seconds ago, wait before showing another.

```python
    max_events_per_cycle: int = 100
```

Maximum number of raw events the OBSERVE node processes per OODA cycle. Prevents memory blowup if there's a sudden burst of events. The truncation happens at `raw_events[-100:]` in `observe_node`.

```python
    wisdom_cache_ttl: int = 300
```

Time-to-live (in seconds, 5 minutes) for cached wisdom store queries. Wisdom records change slowly (only when an intervention's effectiveness is measured), so caching reduces DB load.

```python
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
```

Pydantic v2 config: tells `BaseSettings` to look for a `.env` file in the current directory and load values from it. UTF-8 encoding ensures special characters in passwords work correctly.

```python
@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**Singleton factory.** `@lru_cache` means this function is called only once; subsequent calls return the cached result. This is important because `Settings()` reads `.env` and checks env vars every time — caching avoids repeated I/O.

## How It Connects

Every module in the codebase uses `get_settings()`:

```python
# src/db/engine.py
from src.config.settings import get_settings
settings = get_settings()
engine = create_async_engine(settings.database_url)

# src/llm/provider.py
from src.config.settings import get_settings
settings = get_settings()
# uses settings.openai_api_key, settings.anthropic_api_key, etc.

# src/api/dependencies.py
from src.config.settings import get_settings
settings = get_settings()
# uses settings.redis_url to connect to Redis

# src/ingestion/consumer.py
from src.config.settings import get_settings
settings = get_settings()
# uses settings.redis_stream_observation, etc.
```

## PoC Presentation Idea

Run this live:

```python
from src.config.settings import get_settings
s1 = get_settings()
s2 = get_settings()
print(s1 is s2)  # True — singleton pattern
print(s1.database_url)      # postgresql+asyncpg://ab6:ab6_pass@localhost:5432/ab6_ai
print(s1.llm_rate_limit_rpm) # 100
```

Then set `$env:LOG_LEVEL="DEBUG"` and show that `get_settings().log_level` changes. This demonstrates the env-var-override mechanism.
