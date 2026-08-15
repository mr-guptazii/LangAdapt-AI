from functools import lru_cache

from app.ai.providers.base import EmbeddingProvider, LLMProvider
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache
def get_llm_provider() -> LLMProvider:
    if settings.LLM_PROVIDER == "anthropic" and settings.ANTHROPIC_API_KEY:
        from app.ai.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    if settings.LLM_PROVIDER == "anthropic" and not settings.ANTHROPIC_API_KEY:
        logger.warning("llm_fallback_to_mock", reason="LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set")

    if settings.LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY:
        # Despite the name, this covers any OpenAI-Chat-Completions-compatible
        # backend — NVIDIA NIM, Gemini's OpenAI-compat endpoint, real OpenAI,
        # Groq, etc. — selected by OPENAI_BASE_URL, not by this provider name.
        from app.ai.providers.openai_compatible_provider import OpenAICompatibleProvider
        return OpenAICompatibleProvider()
    if settings.LLM_PROVIDER == "openai" and not settings.OPENAI_API_KEY:
        logger.warning("llm_fallback_to_mock", reason="LLM_PROVIDER=openai but OPENAI_API_KEY is not set")

    from app.ai.providers.mock_provider import MockLLMProvider
    return MockLLMProvider()


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    from app.ai.providers.mock_provider import MockEmbeddingProvider
    # A real embedding provider (e.g. Voyage/OpenAI) can be plugged in here behind
    # the same EmbeddingProvider interface; mock keeps local dev dependency-free.
    return MockEmbeddingProvider(dim=settings.EMBEDDING_DIM)
