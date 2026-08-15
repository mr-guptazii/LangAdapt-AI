"""Real Anthropic-backed provider. Structured output is implemented via forced
tool-use (a single tool whose input_schema is the Pydantic model's JSON schema),
which is the reliable way to get validated JSON out of Claude — we never regex
or best-effort-parse free text for anything that drives a decision.
"""
from typing import TypeVar

import anthropic
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from app.ai.providers.base import LLMMessage, LLMProvider, LLMResult, LLMUsage, ModelTier
from app.core.config import settings

T = TypeVar("T", bound=BaseModel)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    def _model_for(self, tier: ModelTier) -> str:
        return settings.ANTHROPIC_MODEL_STRONG if tier == ModelTier.STRONG else settings.ANTHROPIC_MODEL_FAST

    def _split(self, messages: list[LLMMessage]) -> tuple[str, list[dict]]:
        system = "\n".join(m.content for m in messages if m.role == "system")
        turns = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        return system, turns

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def complete(self, messages: list[LLMMessage], tier: ModelTier = ModelTier.FAST, max_tokens: int = 1024) -> LLMResult:
        system, turns = self._split(messages)
        model = self._model_for(tier)
        resp = await self._client.messages.create(
            model=model, max_tokens=max_tokens, system=system or None, messages=turns
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        usage = LLMUsage(
            input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens, provider=self.name, model=model
        )
        return LLMResult(text=text, usage=usage)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def structured(
        self, messages: list[LLMMessage], response_model: type[T], tier: ModelTier = ModelTier.FAST, max_tokens: int = 1024
    ) -> tuple[T, LLMUsage]:
        system, turns = self._split(messages)
        model = self._model_for(tier)
        schema = response_model.model_json_schema()
        tool_name = f"emit_{response_model.__name__.lower()}"
        resp = await self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system or None,
            messages=turns,
            tools=[{"name": tool_name, "description": "Emit the structured result.", "input_schema": schema}],
            tool_choice={"type": "tool", "name": tool_name},
        )
        tool_use = next(b for b in resp.content if b.type == "tool_use")
        instance = response_model.model_validate(tool_use.input)
        usage = LLMUsage(
            input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens, provider=self.name, model=model
        )
        return instance, usage
