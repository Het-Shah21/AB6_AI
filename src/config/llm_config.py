from pydantic import BaseModel
from typing import Literal


class LLMProviderConfig(BaseModel):
    model: str
    provider: Literal["openai", "anthropic", "google_genai"]


LLM_CONFIG: dict[str, LLMProviderConfig] = {
    "primary": LLMProviderConfig(
        model="gpt-4o-mini",
        provider="openai",
    ),
    "reasoning": LLMProviderConfig(
        model="gpt-4o",
        provider="openai",
    ),
    "fallback_1": LLMProviderConfig(
        model="claude-sonnet-4-20250514",
        provider="anthropic",
    ),
    "fallback_2": LLMProviderConfig(
        model="gemini-2.5-flash",
        provider="google_genai",
    ),
    "embedding": LLMProviderConfig(
        model="text-embedding-3-small",
        provider="openai",
    ),
}
