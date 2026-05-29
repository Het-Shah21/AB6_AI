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

logger = logging.getLogger(__name__)

rate_limiter = RateLimiter(rpm=get_settings().llm_rate_limit_rpm)


def _build_model_key(config: LLMProviderConfig) -> str:
    return f"{config.provider}:{config.model}"


async def get_llm(purpose: str = "primary") -> BaseChatModel:
    config = LLM_CONFIG.get(purpose)
    if config is None:
        config = LLM_CONFIG["primary"]
    return init_chat_model(
        model=_build_model_key(config),
        temperature=0.3,
    )


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


async def get_llm_for_purpose(purpose: str = "primary") -> BaseChatModel:
    return await get_llm_with_fallback(purpose)


async def get_embedding_model() -> Embeddings:
    settings = get_settings()
    return OpenAIEmbeddings(
        model=settings.llm_embedding_model,
        api_key=settings.openai_api_key,
    )


async def llm_call(
    purpose: str,
    messages: list[dict[str, Any]],
    **kwargs: Any,
) -> str:
    llm = await get_llm_for_purpose(purpose)
    result = await llm.ainvoke(messages, **kwargs)
    return str(result.content)
