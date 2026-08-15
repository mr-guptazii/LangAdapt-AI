import json
from types import SimpleNamespace

import pytest

from app.ai.providers.base import LLMMessage
from app.ai.providers.openai_compatible_provider import (
    _MIN_STRUCTURED_MAX_TOKENS,
    OpenAICompatibleProvider,
    _infer_provider_name,
)
from app.core.config import settings
from app.schemas.agent_io import ConversationOutput


class _FakeCompletions:
    def __init__(self, response):
        self._response = response
        self.last_kwargs: dict | None = None

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self._response


class _FakeClient:
    def __init__(self, response):
        self.chat = SimpleNamespace(completions=_FakeCompletions(response))


def _usage(prompt=10, completion=20):
    return SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion)


def _text_response(text: str):
    message = SimpleNamespace(content=text, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=_usage())


def _tool_call_response(arguments: dict):
    function = SimpleNamespace(name="emit_conversationoutput", arguments=json.dumps(arguments))
    message = SimpleNamespace(content=None, tool_calls=[SimpleNamespace(function=function)])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=_usage())


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")


def test_infer_provider_name_recognizes_known_hosts():
    assert _infer_provider_name("https://integrate.api.nvidia.com/v1") == "nvidia"
    assert _infer_provider_name("https://generativelanguage.googleapis.com/v1beta/openai/") == "gemini"
    assert _infer_provider_name("https://api.groq.com/openai/v1") == "groq"
    assert _infer_provider_name(None) == "openai"
    assert _infer_provider_name("https://my-local-vllm:8000/v1") == "openai_compatible"


@pytest.mark.asyncio
async def test_complete_returns_text_and_usage(monkeypatch):
    fake_response = _text_response("Hi, how can I help?")
    monkeypatch.setattr(
        "app.ai.providers.openai_compatible_provider.AsyncOpenAI", lambda **kwargs: _FakeClient(fake_response)
    )
    provider = OpenAICompatibleProvider()
    result = await provider.complete([LLMMessage(role="user", content="hi")])
    assert result.text == "Hi, how can I help?"
    assert result.usage.input_tokens == 10
    assert result.usage.output_tokens == 20


@pytest.mark.asyncio
async def test_structured_parses_tool_call_into_validated_model(monkeypatch):
    payload = {
        "response": "Great!", "follow_up_question": "What next?",
        "correction_needed": False, "correction_priority": "none", "teaching_intent": "general_conversation",
    }
    fake_response = _tool_call_response(payload)
    monkeypatch.setattr(
        "app.ai.providers.openai_compatible_provider.AsyncOpenAI", lambda **kwargs: _FakeClient(fake_response)
    )
    provider = OpenAICompatibleProvider()
    instance, usage = await provider.structured([LLMMessage(role="user", content="hi")], ConversationOutput)
    assert isinstance(instance, ConversationOutput)
    assert instance.response == "Great!"
    assert instance.follow_up_question == "What next?"
    assert usage.output_tokens == 20


@pytest.mark.asyncio
async def test_provider_name_reflects_configured_base_url(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_BASE_URL", "https://integrate.api.nvidia.com/v1")
    fake_response = _text_response("hi")
    monkeypatch.setattr(
        "app.ai.providers.openai_compatible_provider.AsyncOpenAI", lambda **kwargs: _FakeClient(fake_response)
    )
    provider = OpenAICompatibleProvider()
    assert provider.name == "nvidia"


@pytest.mark.asyncio
async def test_structured_falls_back_to_json_in_content_when_tool_not_called(monkeypatch):
    """Some OpenAI-compatible backends (observed against Gemini's compat layer)
    don't reliably honor a forced tool_choice and answer in plain content
    instead — this must not crash, it should recover the JSON from the text."""
    payload = {
        "response": "Fine, thanks!", "follow_up_question": "And you?",
        "correction_needed": False, "correction_priority": "none", "teaching_intent": "general_conversation",
    }
    fake_response = _text_response(f"Here you go: {json.dumps(payload)}")
    monkeypatch.setattr(
        "app.ai.providers.openai_compatible_provider.AsyncOpenAI", lambda **kwargs: _FakeClient(fake_response)
    )
    provider = OpenAICompatibleProvider()
    instance, _usage = await provider.structured([LLMMessage(role="user", content="hi")], ConversationOutput)
    assert instance.response == "Fine, thanks!"


@pytest.mark.asyncio
async def test_structured_raises_clear_error_when_no_usable_data(monkeypatch):
    fake_response = _text_response("Sorry, I can't help with that.")
    monkeypatch.setattr(
        "app.ai.providers.openai_compatible_provider.AsyncOpenAI", lambda **kwargs: _FakeClient(fake_response)
    )
    provider = OpenAICompatibleProvider()
    with pytest.raises(RuntimeError, match="neither a tool call"):
        await provider.structured([LLMMessage(role="user", content="hi")], ConversationOutput)


@pytest.mark.asyncio
async def test_structured_enforces_min_token_floor_for_reasoning_models(monkeypatch):
    """A caller-requested max_tokens of 300 (sized for non-reasoning models
    like Claude/GPT) must be raised to the floor — otherwise a reasoning model
    can silently burn the whole budget on hidden thinking tokens and never
    reach the actual tool call (reproduced live against gemini-3.6-flash)."""
    payload = {
        "response": "Fine!", "follow_up_question": "You?",
        "correction_needed": False, "correction_priority": "none", "teaching_intent": "general_conversation",
    }
    fake_response = _tool_call_response(payload)
    fake_client = _FakeClient(fake_response)
    monkeypatch.setattr("app.ai.providers.openai_compatible_provider.AsyncOpenAI", lambda **kwargs: fake_client)
    provider = OpenAICompatibleProvider()
    await provider.structured([LLMMessage(role="user", content="hi")], ConversationOutput, max_tokens=300)
    assert fake_client.chat.completions.last_kwargs["max_tokens"] == _MIN_STRUCTURED_MAX_TOKENS
