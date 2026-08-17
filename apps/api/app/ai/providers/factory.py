from functools import lru_cache

from app.ai.providers.base import EmbeddingProvider, LLMProvider
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache
def get_llm_provider() -> LLMProvider:
    from app.ai.providers.mock_provider import MockLLMProvider

    if settings.LLM_PROVIDER == "anthropic" and settings.ANTHROPIC_API_KEY:
        from app.ai.providers.anthropic_provider import AnthropicProvider
        from app.ai.providers.resilient_provider import ResilientLLMProvider
        # Falls back to the mock provider (real deterministic logic, zero
        # external calls) if the real one fails for any reason — most
        # commonly a rate-limited/quota-exhausted key (observed repeatedly
        # in production). Every caller already handles is_mock honestly.
        return ResilientLLMProvider(AnthropicProvider(), MockLLMProvider())
    if settings.LLM_PROVIDER == "anthropic" and not settings.ANTHROPIC_API_KEY:
        logger.warning("llm_fallback_to_mock", reason="LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set")

    if settings.LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY:
        # Despite the name, this covers any OpenAI-Chat-Completions-compatible
        # backend — NVIDIA NIM, Gemini's OpenAI-compat endpoint, real OpenAI,
        # Groq, etc. — selected by OPENAI_BASE_URL, not by this provider name.
        from app.ai.providers.openai_compatible_provider import OpenAICompatibleProvider
        from app.ai.providers.resilient_provider import ResilientLLMProvider
        return ResilientLLMProvider(OpenAICompatibleProvider(), MockLLMProvider())
    if settings.LLM_PROVIDER == "openai" and not settings.OPENAI_API_KEY:
        logger.warning("llm_fallback_to_mock", reason="LLM_PROVIDER=openai but OPENAI_API_KEY is not set")

    return MockLLMProvider()


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    if settings.EMBEDDING_PROVIDER == "mock":
        from app.ai.providers.mock_provider import MockEmbeddingProvider
        return MockEmbeddingProvider(dim=settings.EMBEDDING_DIM)

    # Default: a real (not random) lexical embedding — see lexical_provider.py's
    # docstring for why this replaced an unconditional mock return that ran even
    # in production. A future real neural/API-backed provider can be added here
    # behind the same EmbeddingProvider interface without touching call sites.
    from app.ai.providers.lexical_provider import HashingLexicalEmbeddingProvider
    return HashingLexicalEmbeddingProvider(dim=settings.EMBEDDING_DIM)
