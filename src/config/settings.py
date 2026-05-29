from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://ab6:ab6_pass@localhost:5432/ab6_ai"
    redis_url: str = "redis://localhost:6379/0"

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    llm_primary_provider: str = "openai"
    llm_primary_model: str = "gpt-4o-mini"
    llm_reasoning_model: str = "gpt-4o"
    llm_fallback_1_provider: str = "anthropic"
    llm_fallback_1_model: str = "claude-sonnet-4-20250514"
    llm_fallback_2_provider: str = "google_genai"
    llm_fallback_2_model: str = "gemini-2.5-flash"
    llm_embedding_model: str = "text-embedding-3-small"

    llm_rate_limit_rpm: int = 100

    sentry_dsn: str = ""
    log_level: str = "INFO"

    redis_stream_observation: str = "ai:observations"
    redis_stream_telemetry: str = "ai:telemetry"
    redis_stream_domain_events: str = "ai:domain_events"

    intervention_cooldown_seconds: int = 60
    max_events_per_cycle: int = 100
    wisdom_cache_ttl: int = 300

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
