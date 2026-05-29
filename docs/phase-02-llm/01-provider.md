# Phase 2 — LLM Integration

## Task 2.1: LLM Provider (`src/llm/provider.py`)

### System Design Reference

Master System Design, "LLM Integration" section. Specified a multi-provider architecture with:
- Primary model for fast decisions (GPT-4o-mini)
- Reasoning model for deep diagnosis (GPT-4o)
- Two fallback providers for resilience (Anthropic, Google)
- Rate limiting to prevent API abuse
- Embedding model for concept vectorization

### Purpose

Initializes LangChain chat models with automatic fallback across 3 providers. This is the central LLM factory — every node that needs an LLM calls `get_llm_for_purpose()` instead of constructing models directly.

### Line-by-Line Explanation

```python
import logging
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from src.config.settings import get_settings
from src.config.llm_config import LLM_CONFIG, LLMProviderConfig
from src.llm.rate_limiter import RateLimiter
from src.shared.exceptions import LLMFallbackExhaustedError
```

- `init_chat_model` — LangChain unified factory. Takes a model string like `"openai:gpt-4o-mini"` and returns the correct `BaseChatModel` subclass.
- `BaseChatModel` — Abstract base class that all LangChain chat models implement. Provides `ainvoke()`, `stream()`, `batch()`.
- `Embeddings` — Abstract base class for embedding models.
- `OpenAIEmbeddings` — Concrete embedding model for OpenAI (used separately from chat models).
- `RateLimiter` — Sliding-window rate limiter per provider.
- `LLMFallbackExhaustedError` — Raised when all providers fail.

```python
logger = logging.getLogger(__name__)
rate_limiter = RateLimiter(rpm=get_settings().llm_rate_limit_rpm)
```

Module-level rate limiter (100 RPM by default). Shared across all LLM calls.

```python
def _build_model_key(config: LLMProviderConfig) -> str:
    return f"{config.provider}:{config.model}"
```

LangChain's `init_chat_model` expects the format `"provider:model"`, e.g., `"openai:gpt-4o-mini"`. This helper constructs that key from a config object.

```python
async def get_llm(purpose: str = "primary") -> BaseChatModel:
    config = LLM_CONFIG.get(purpose)
    if config is None:
        config = LLM_CONFIG["primary"]
    return init_chat_model(
        model=_build_model_key(config),
        temperature=0.3,
    )
```

Simple model getter (no fallback). Used internally. `temperature=0.3` keeps outputs deterministic enough for structured decisions while allowing slight creativity for diagnosis.

```python
async def get_llm_with_fallback(purpose: str = "primary") -> BaseChatModel:
    primary = LLM_CONFIG.get(purpose) or LLM_CONFIG["primary"]
    fallbacks = [
        LLM_CONFIG.get("fallback_1"),
        LLM_CONFIG.get("fallback_2"),
    ]
    fallbacks = [fb for fb in fallbacks if fb is not None]

    models_to_try = [primary, *fallbacks]
    last_error: Exception | None = None

    for config in models_to_try:
        try:
            await rate_limiter.acquire(config.provider)
            return init_chat_model(
                model=_build_model_key(config),
                temperature=0.3,
            )
        except Exception as e:
            logger.warning(
                "LLM provider %s failed: %s. Trying fallback...",
                config.provider,
                e,
            )
            last_error = e

    raise LLMFallbackExhaustedError(
        "All LLM providers exhausted"
    ) from last_error
```

**The fallback chain:**
1. Gets the primary config for the requested purpose
2. Gets fallback_1 and fallback_2 from `LLM_CONFIG`
3. Builds `[primary, fallback_1, fallback_2]` — tries each in order
4. For each attempt:
   - Acquires the rate limiter (waits if at limit)
   - Calls `init_chat_model()` which reads API keys from env vars
   - If it succeeds, returns the model immediately
   - If it fails (wrong API key, network error, rate limit), logs a warning and tries the next
5. If ALL providers fail, raises `LLMFallbackExhaustedError`

**This is why the demo shows 3 "LLM provider failed" warnings** — it tries OpenAI (no key), then Anthropic (no key), then Google (no key), then gives up.

```python
async def get_llm_for_purpose(purpose: str = "primary") -> BaseChatModel:
    return await get_llm_with_fallback(purpose)
```

Public alias. All agent nodes call `get_llm_for_purpose()`.

```python
async def get_embedding_model() -> Embeddings:
    settings = get_settings()
    return OpenAIEmbeddings(
        model=settings.llm_embedding_model,
        api_key=settings.openai_api_key,
    )
```

Creates OpenAI embedding model separately from chat models. The `text-embedding-3-small` model uses a different API endpoint than chat completions.

```python
async def llm_call(
    purpose: str,
    messages: list[dict[str, Any]],
    **kwargs: Any,
) -> str:
    llm = await get_llm_for_purpose(purpose)
    result = await llm.ainvoke(messages, **kwargs)
    return str(result.content)
```

Convenience wrapper: gets a model for the purpose, calls `ainvoke()` with the messages, returns just the content string. Used by the concept graph builder and generation tools.

### How It Connects

```
get_llm_for_purpose("reasoning")  → orient.py  → GPT-4o (diagnosis)
get_llm_for_purpose("primary")    → decide.py  → GPT-4o-mini (intervention selection)
get_embedding_model()             → embeddings.py → text-embedding-3-small (concept vectors)
llm_call()                         → builder.py → LLM extraction
```

---

## Task 2.2: Rate Limiter (`src/llm/rate_limiter.py`)

### Purpose

Sliding-window rate limiter per LLM provider. Prevents hitting API rate limits by tracking request timestamps and sleeping when the limit is reached.

### Line-by-Line

```python
import asyncio
import time
from collections import defaultdict
```

- `asyncio` — For `asyncio.sleep()` when waiting
- `time` — For `time.monotonic()` (monotonic clock, not affected by system time changes)
- `defaultdict` — Auto-creates lists/timestamps for new providers

```python
class RateLimiter:
    def __init__(self, rpm: int = 100):
        self.rpm = rpm
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._timestamps: dict[str, list[float]] = defaultdict(list)
```

- `rpm` — Max requests per minute (configurable via settings)
- `_locks` — Per-provider asyncio lock. Each provider has its own lock so rate limits don't cascade across providers.
- `_timestamps` — Per-provider list of recent request timestamps. Used to count RPM.

```python
    async def acquire(self, provider: str) -> None:
        async with self._locks[provider]:
            now = time.monotonic()
            window = 60.0
            cutoff = now - window
            self._timestamps[provider] = [
                ts for ts in self._timestamps[provider] if ts > cutoff
            ]
            while len(self._timestamps[provider]) >= self.rpm:
                sleep_time = self._timestamps[provider][0] + window - now
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                now = time.monotonic()
                cutoff = now - window
                self._timestamps[provider] = [
                    ts for ts in self._timestamps[provider] if ts > cutoff
                ]
            self._timestamps[provider].append(now)
```

**Sliding window algorithm:**
1. Acquires the per-provider lock (only one request per provider at a time)
2. Removes timestamps older than 60 seconds (the "sliding" part)
3. If count ≥ RPM, calculates how long until the oldest request falls out of the window
4. Sleeps for that duration
5. Appends current timestamp

### How It Connects

Called by `provider.py` before every `init_chat_model()` call. Ensures we never exceed 100 RPM per provider.

---

## Task 2.3: PII Sanitizer (`src/llm/sanitizer.py`)

### Purpose

Strips personally identifiable information (PII) from data before it reaches the LLM. This prevents student names, emails, and phone numbers from being sent to third-party API providers.

### Line-by-Line

```python
import re
from typing import Any
```

- `re` — Regular expressions for pattern matching
- `Any` — Type hint for dict values

```python
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(r"\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}")
CC_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
NAME_PATTERN = re.compile(r"(?i)\b(?:name|user|student)\s*[:\s]\s*[A-Z][a-z]+(?:\s[A-Z][a-z]+)?")
```

**Four PII regex patterns:**
- `EMAIL_PATTERN` — Matches standard email format
- `PHONE_PATTERN` — Matches international phone numbers with optional country code
- `CC_PATTERN` — Matches 13-16 digit sequences (potential credit card numbers)
- `NAME_PATTERN` — Matches patterns like `"name: John Doe"` or `"user: Alice"`. The `(?i)` flag makes it case-insensitive. The word boundary `\b` prevents matching inside larger words.

**Design note on NAME_PATTERN:** The original version was just `[A-Z][a-z]+ [A-Z][a-z]+` (any two capitalized words), which was too aggressive — it matched concept names like "Inverse Kinematics" and "Forward Kinematics". The fix added the prefix context `name:|user:|student` to only match labeled names.

```python
def strip_pii(text: str) -> str:
    text = EMAIL_PATTERN.sub("[REDACTED-EMAIL]", text)
    text = PHONE_PATTERN.sub("[REDACTED-PHONE]", text)
    text = CC_PATTERN.sub("[REDACTED-CC]", text)
    text = NAME_PATTERN.sub("[REDACTED-NAME]", text)
    return text
```

Applies all 4 patterns sequentially. Each pattern replaces matches with a labeled `[REDACTED-*]` token so downstream code knows what was removed.

```python
def sanitize_observation_event(event: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(event)
    for field in ["user_id", "session_id"]:
        if field in sanitized:
            sanitized[field] = strip_pii(str(sanitized[field]))
    if "metadata" in sanitized and isinstance(sanitized["metadata"], dict):
        sanitized["metadata"] = {
            k: strip_pii(str(v)) if isinstance(v, str) else v
            for k, v in sanitized["metadata"].items()
        }
    return sanitized
```

Sanitizes observation events before they enter the OODA pipeline. Strips PII from `user_id`, `session_id`, and all metadata string values.

```python
def sanitize_learner_summary(summary: dict[str, Any]) -> dict[str, Any]:
    serialized = json.dumps(summary)
    cleaned = strip_pii(serialized)
    return json.loads(cleaned)
```

Sanitizes the entire learner summary before sending it to the LLM for diagnosis. Serializes to JSON, strips PII from the entire string, then deserializes back.

### How It Connects

```
PII Middleware (src/api/middleware/sanitizer.py) → strips PII from API requests
sanitize_observation_event() → called by event router before pushing to Redis
sanitize_learner_summary() → called by ORIENT node before LLM diagnosis
```

### PoC Presentation Idea

```python
from src.llm.sanitizer import strip_pii

text = "Student John Smith (john.smith@email.com) scored 30% on challenge_1"
print(strip_pii(text))
# "Student [REDACTED-NAME] ([REDACTED-EMAIL]) scored 30% on challenge_1"
```

Show that concept names like "Inverse Kinematics" are NOT stripped (the NAME_PATTERN requires a prefix context).
