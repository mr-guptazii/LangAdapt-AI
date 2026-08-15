import pytest
from pydantic import BaseModel

from app.ai.providers.base import LLMMessage
from app.ai.providers.mock_provider import MockEmbeddingProvider, MockLLMProvider
from app.schemas.agent_io import ConversationOutput, ErrorAnalysisOutput


class Dummy(BaseModel):
    response: str
    correction_needed: bool


@pytest.mark.asyncio
async def test_mock_complete_returns_text():
    provider = MockLLMProvider()
    result = await provider.complete([LLMMessage(role="user", content="hello")])
    assert isinstance(result.text, str) and len(result.text) > 0
    assert result.usage.provider == "mock"


@pytest.mark.asyncio
async def test_mock_structured_returns_validated_model():
    provider = MockLLMProvider()
    instance, usage = await provider.structured(
        [LLMMessage(role="user", content="I go yesterday.")], ConversationOutput
    )
    assert isinstance(instance, ConversationOutput)
    assert usage.provider == "mock"


@pytest.mark.asyncio
async def test_mock_detects_past_tense_error_pattern():
    """The mock provider must actually exercise the agent graph's error-detection
    path (not just return structurally valid junk) so local dev without an API key
    still demonstrates the core differentiator end-to-end."""
    provider = MockLLMProvider()
    instance, _usage = await provider.structured(
        [LLMMessage(role="user", content="Yesterday I go to the market.")], ErrorAnalysisOutput
    )
    assert isinstance(instance, ErrorAnalysisOutput)
    assert len(instance.errors) >= 1
    assert instance.errors[0].category == "past_tense"
    assert instance.errors[0].correct == "went"


@pytest.mark.asyncio
async def test_mock_embedding_is_deterministic_and_unit_normalized():
    provider = MockEmbeddingProvider(dim=16)
    v1 = await provider.embed("past tense mistake")
    v2 = await provider.embed("past tense mistake")
    assert v1 == v2
    norm = sum(x * x for x in v1) ** 0.5
    assert abs(norm - 1.0) < 1e-6
