# Task 1.4 — LLM Provider Configuration: `src/config/llm_config.py`

## System Design Reference

Master System Design, "LLM Configuration" section. The design specified a typed mapping from usage "purpose" to provider+model pairs, allowing the system to use different models for different tasks (fast/cheap for decisions, smart/expensive for diagnosis).

## Purpose

Defines the `LLM_CONFIG` dictionary that maps 5 purposes (`primary`, `reasoning`, `fallback_1`, `fallback_2`, `embedding`) to `LLMProviderConfig` objects. This is the routing table that `src/llm/provider.py` uses to decide which model to call for each task.

## Line-by-Line Explanation

```python
from pydantic import BaseModel
```

Pydantic's base class for data validation. Every config object is type-checked at creation time.

```python
from typing import Literal
```

Python 3.8+ typing feature. `Literal["openai", "anthropic", "google_genai"]` means the `provider` field can ONLY be one of those three strings. Any other value causes a Pydantic validation error.

```python
class LLMProviderConfig(BaseModel):
    model: str
    provider: Literal["openai", "anthropic", "google_genai"]
```

A typed config object with two fields:
- `model: str` — The model name (e.g., `"gpt-4o-mini"`, `"claude-sonnet-4-20250514"`)
- `provider: Literal[...]` — The provider identifier. LangChain's `init_chat_model()` uses this to select the correct SDK.

The `Literal` type is important: it prevents typos. Writing `provider="openai"` works; writing `provider="opeanai"` raises a `ValidationError` at startup.

```python
LLM_CONFIG: dict[str, LLMProviderConfig] = {
    "primary": LLMProviderConfig(
        model="gpt-4o-mini",
        provider="openai",
    ),
```

**Primary** — The default model used for most LLM calls (DECIDE node, tool calls). `gpt-4o-mini` is OpenAI's fastest and cheapest model (~$0.15/1M input tokens). It's good enough for structured JSON output and simple reasoning.

```python
    "reasoning": LLMProviderConfig(
        model="gpt-4o",
        provider="openai",
    ),
```

**Reasoning** — Used by the ORIENT node for learner diagnosis. `gpt-4o` is OpenAI's most capable model (~$2.50/1M input tokens). Diagnosis requires deeper reasoning (connecting error patterns to conceptual gaps), so the smarter model is justified.

```python
    "fallback_1": LLMProviderConfig(
        model="claude-sonnet-4-20250514",
        provider="anthropic",
    ),
```

**Fallback 1** — Anthropic Claude Sonnet 4. If OpenAI is down or rate-limited, the system falls back to Anthropic. This model has a 200K context window (useful for long learner histories) and different API availability zones.

```python
    "fallback_2": LLMProviderConfig(
        model="gemini-2.5-flash",
        provider="google_genai",
    ),
```

**Fallback 2** — Google Gemini 2.5 Flash. If both OpenAI and Anthropic fail, try Google. This is the "ultimate fallback" provider — three completely independent API services make simultaneous outage extremely unlikely.

```python
    "embedding": LLMProviderConfig(
        model="text-embedding-3-small",
        provider="openai",
    ),
```

**Embedding** — Separate from chat models. `text-embedding-3-small` generates 1536-dimensional vectors at ~$0.02/1M tokens. Used by the concept graph builder to create searchable embeddings. Although configured as an `LLMProviderConfig`, it's initialized via `OpenAIEmbeddings` (not `init_chat_model`) in `provider.py`.

## How It Connects

```
src/llm/provider.py
    │
    ├── get_llm(purpose="primary")
    │   → LLM_CONFIG["primary"] → init_chat_model("openai:gpt-4o-mini")
    │
    ├── get_llm_with_fallback(purpose="reasoning")
    │   → [LLM_CONFIG["reasoning"], LLM_CONFIG["fallback_1"], LLM_CONFIG["fallback_2"]]
    │   → tries each in order until one succeeds
    │
    └── get_embedding_model()
        → LLM_CONFIG["embedding"] → OpenAIEmbeddings(model="text-embedding-3-small")

Agent nodes call:
    orient.py → get_llm_for_purpose("reasoning") → GPT-4o
    decide.py → get_llm_for_purpose("primary")    → GPT-4o-mini
```

## PoC Presentation Idea

Show the fallback chain as a diagram:

```
ORIENT needs a diagnosis
    │
    ├─→ Try GPT-4o (OpenAI)
    │     ├─ Success → return diagnosis
    │     └─ Fail → log warning
    │
    ├─→ Try Claude Sonnet 4 (Anthropic)
    │     ├─ Success → return diagnosis
    │     └─ Fail → log warning
    │
    └─→ Try Gemini 2.5 Flash (Google)
          ├─ Success → return diagnosis
          └─ Fail → raise LLMFallbackExhaustedError
                ↓
          orient.py catches exception → hardcoded fallback text
```

This demonstrates **defense in depth** — three independent LLM providers, each with different infrastructure, so the system keeps working even if one API is down.
