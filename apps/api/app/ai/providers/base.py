"""Provider-agnostic LLM interface (section 21).

Business logic (agents, prompts) depends only on this interface, never on a
specific vendor SDK. Swap providers via LLM_PROVIDER env var; no code changes.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ModelTier(str, Enum):
    """Cost-routing tier (section 42). FAST for cheap classification-style calls,
    STRONG for complex teaching/conversation decisions."""
    FAST = "fast"
    STRONG = "strong"


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    provider: str = ""
    model: str = ""


@dataclass
class LLMResult:
    text: str
    usage: LLMUsage = field(default_factory=LLMUsage)


class LLMProvider(ABC):
    """All methods are async. structured() must return validated Pydantic models —
    we never hand-parse free-form LLM prose for anything that drives a decision."""

    name: str = "base"

    @abstractmethod
    async def complete(
        self, messages: list[LLMMessage], tier: ModelTier = ModelTier.FAST, max_tokens: int = 1024
    ) -> LLMResult: ...

    @abstractmethod
    async def structured(
        self,
        messages: list[LLMMessage],
        response_model: type[T],
        tier: ModelTier = ModelTier.FAST,
        max_tokens: int = 1024,
    ) -> tuple[T, LLMUsage]: ...


class EmbeddingProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def embed(self, text: str) -> list[float]: ...
