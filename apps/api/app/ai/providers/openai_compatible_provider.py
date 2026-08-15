"""Real provider for any OpenAI-Chat-Completions-compatible API — NVIDIA NIM
(integrate.api.nvidia.com), Google Gemini's OpenAI-compatibility endpoint
(generativelanguage.googleapis.com/.../openai/), real OpenAI, Groq, Together,
a local vLLM/Ollama server exposing an OpenAI-shaped API, etc. Which actual
backend gets hit is entirely a config change (OPENAI_BASE_URL + OPENAI_API_KEY)
— none of this file is vendor-specific.

Structured output uses forced function-calling (a single tool whose parameters
schema is the Pydantic model's JSON schema), the OpenAI-API equivalent of the
tool-use pattern AnthropicProvider uses — same reliability rationale: never
regex/best-effort-parse free text for anything that drives a decision. This
depends on the selected backend/model actually supporting function calling;
most mainstream instruct models on NIM, Gemini, and OpenAI itself do, but it's
worth checking for less common models.
"""
import json
import re
from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from app.ai.providers.base import LLMMessage, LLMProvider, LLMResult, LLMUsage, ModelTier
from app.core.config import settings

T = TypeVar("T", bound=BaseModel)

# Some OpenAI-compatible backends route through a "thinking"/reasoning model
# whose hidden reasoning tokens are deducted from the SAME max_tokens budget
# as the visible output (observed live against gemini-3.6-flash: a 300-token
# budget was entirely consumed by ~800 tokens of internal reasoning before the
# model could even start the actual tool call, producing a truncated/malformed
# function call). Our agent nodes size max_tokens for non-reasoning models
# (Claude, GPT), so this provider enforces its own floor underneath whatever
# the caller requested — cheap insurance against silent truncation, and a
# no-op for backends without hidden reasoning overhead (unused headroom, not
# forced spend — the model still stops at its natural response length).
_MIN_STRUCTURED_MAX_TOKENS = 4096

# Purely cosmetic: lets the admin AI-usage dashboard (grouped by provider+model)
# distinguish "NVIDIA via the OpenAI-compatible path" from "Gemini via the
# OpenAI-compatible path" instead of lumping every backend under one label.
_KNOWN_HOSTS = {
    "integrate.api.nvidia.com": "nvidia",
    "generativelanguage.googleapis.com": "gemini",
    "api.groq.com": "groq",
    "api.together.xyz": "together",
    "api.openai.com": "openai",
}


def _infer_provider_name(base_url: str | None) -> str:
    if not base_url:
        return "openai"
    lowered = base_url.lower()
    for host, name in _KNOWN_HOSTS.items():
        if host in lowered:
            return name
    return "openai_compatible"


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self) -> None:
        self.name = _infer_provider_name(settings.OPENAI_BASE_URL)
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)

    def _model_for(self, tier: ModelTier) -> str:
        return settings.OPENAI_MODEL_STRONG if tier == ModelTier.STRONG else settings.OPENAI_MODEL_FAST

    def _to_openai_messages(self, messages: list[LLMMessage]) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in messages]

    def _usage_from(self, resp, model: str) -> LLMUsage:
        usage = resp.usage
        return LLMUsage(
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            provider=self.name, model=model,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def complete(self, messages: list[LLMMessage], tier: ModelTier = ModelTier.FAST, max_tokens: int = 1024) -> LLMResult:
        model = self._model_for(tier)
        resp = await self._client.chat.completions.create(
            model=model, max_tokens=max_tokens, messages=self._to_openai_messages(messages),
        )
        text = resp.choices[0].message.content or ""
        return LLMResult(text=text, usage=self._usage_from(resp, model))

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8),
        # RuntimeError here means "this backend/model didn't produce usable
        # structured output" — a deterministic failure that will fail the
        # same way on every attempt, not a transient one. Retrying it just
        # triples the latency and API cost for a guaranteed-to-fail call
        # (observed live: 3 retries, 3 more billed requests, same result).
        retry=retry_if_not_exception_type(RuntimeError),
    )
    async def structured(
        self, messages: list[LLMMessage], response_model: type[T], tier: ModelTier = ModelTier.FAST, max_tokens: int = 1024
    ) -> tuple[T, LLMUsage]:
        model = self._model_for(tier)
        schema = response_model.model_json_schema()
        tool_name = f"emit_{response_model.__name__.lower()}"
        resp = await self._client.chat.completions.create(
            model=model,
            max_tokens=max(max_tokens, _MIN_STRUCTURED_MAX_TOKENS),
            messages=self._to_openai_messages(messages),
            tools=[{
                "type": "function",
                "function": {"name": tool_name, "description": "Emit the structured result.", "parameters": schema},
            }],
            tool_choice={"type": "function", "function": {"name": tool_name}},
        )
        message = resp.choices[0].message
        raw_args = self._extract_structured_payload(message, tool_name)
        instance = response_model.model_validate(json.loads(raw_args))
        return instance, self._usage_from(resp, model)

    def _extract_structured_payload(self, message, tool_name: str) -> str:
        """Not every OpenAI-compatible backend honors a forced tool_choice with
        the same fidelity OpenAI itself does — observed in practice against
        Gemini's compatibility layer, which can return a plain-text response
        instead of invoking the tool despite tool_choice requiring it. Falls
        back to extracting a JSON object from the message content rather than
        crashing on a None tool_calls list; still raises a clear, actionable
        error (not a bare AttributeError/TypeError) if neither path has usable
        data, since silently returning empty/garbage data would be worse than
        failing loudly for something that drives a learner-facing decision."""
        if message.tool_calls:
            return message.tool_calls[0].function.arguments

        content = message.content or ""
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return match.group(0)

        raise RuntimeError(
            f"OpenAI-compatible backend '{self.name}' returned neither a tool call for '{tool_name}' "
            f"nor JSON-shaped content — got: {content[:200]!r}. This model/backend may not reliably "
            "support forced function calling; try a different OPENAI_MODEL_FAST/STRONG."
        )
