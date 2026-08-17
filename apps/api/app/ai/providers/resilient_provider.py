"""Wraps a real LLMProvider with an automatic fallback to the deterministic
mock provider when the real one fails for any reason — most commonly a
rate-limited or quota-exhausted API key, observed repeatedly in production
(Groq's daily token quota). Every agent node already has its own hardcoded
"sorry, something went wrong" fallback for exactly this failure, but those
throw away real functionality (mock_provider.py's error detection, exercise
bank, etc. still work with zero external calls) in favor of a blank apology.
This makes the whole app degrade to that real (if generic) functionality
instead, while staying honest about it: MockLLMProvider reports
usage.provider == "mock", and every caller in this codebase already checks
for that (see chat_service.send_message's is_mock computation) — nothing
about this fallback can silently pass mock output off as personalized.
"""
from typing import TypeVar

from pydantic import BaseModel

from app.ai.providers.base import LLMMessage, LLMProvider, LLMResult, LLMUsage, ModelTier
from app.core.logging import get_logger

T = TypeVar("T", bound=BaseModel)

logger = get_logger(__name__)


class ResilientLLMProvider(LLMProvider):
    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self.primary = primary
        self.fallback = fallback
        self.name = primary.name

    async def complete(
        self, messages: list[LLMMessage], tier: ModelTier = ModelTier.FAST, max_tokens: int = 1024
    ) -> LLMResult:
        try:
            return await self.primary.complete(messages, tier=tier, max_tokens=max_tokens)
        except Exception:
            logger.warning("llm_primary_failed_falling_back_to_mock", provider=self.primary.name, exc_info=True)
            return await self.fallback.complete(messages, tier=tier, max_tokens=max_tokens)

    async def structured(
        self, messages: list[LLMMessage], response_model: type[T], tier: ModelTier = ModelTier.FAST, max_tokens: int = 1024
    ) -> tuple[T, LLMUsage]:
        try:
            return await self.primary.structured(messages, response_model, tier=tier, max_tokens=max_tokens)
        except Exception:
            logger.warning("llm_primary_failed_falling_back_to_mock", provider=self.primary.name, exc_info=True)
            return await self.fallback.structured(messages, response_model, tier=tier, max_tokens=max_tokens)
