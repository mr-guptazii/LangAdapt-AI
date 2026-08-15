# AI System

## Provider abstraction

`app/ai/providers/base.py` defines the contract every agent depends on:

```python
class LLMProvider(ABC):
    async def complete(self, messages, tier, max_tokens) -> LLMResult: ...
    async def structured(self, messages, response_model: type[T], tier, max_tokens) -> tuple[T, LLMUsage]: ...
```

- **`AnthropicProvider`** (`anthropic_provider.py`) — structured output via forced tool-use (a single tool whose `input_schema` is the Pydantic model's JSON schema). This is the reliable way to get validated JSON from Claude; free-form text is never regex-parsed for anything that drives a decision.
- **`OpenAICompatibleProvider`** (`openai_compatible_provider.py`) — the same forced-structured-output pattern (OpenAI-style function calling), but against *any* backend that speaks the OpenAI Chat Completions API. Selected via `LLM_PROVIDER=openai`; which actual backend answers is purely `OPENAI_BASE_URL` + `OPENAI_API_KEY` — real OpenAI, NVIDIA NIM, Gemini's OpenAI-compat endpoint, Groq, Together, a local vLLM/Ollama server, all work through this one class. `_infer_provider_name()` maps known hosts (`integrate.api.nvidia.com` → `nvidia`, `generativelanguage.googleapis.com` → `gemini`, etc.) to a readable label purely so the admin AI-usage dashboard can tell them apart when you switch between them. Requires the selected model to support function/tool calling — see `.env.example` for concrete NVIDIA/Gemini model examples known to support it.
- **`MockLLMProvider`** (`mock_provider.py`) — dependency-free, deterministic. It really does detect the `go → went` pattern (and 8 other common irregular verbs — `have` was deliberately excluded after the evaluation framework caught it producing a false positive, see TESTING.md) when "yesterday"/"ago"/"last" appears in the message, populates practice exercises from a small curated bank, and echoes the *real, already-ranked* recommendation candidates back (parsed out of the prompt text) rather than inventing unrelated activities. This is what lets the entire agentic demo — including error detection and mastery updates — work with zero API keys. Conversation replies and follow-up questions are drawn from pools of 10 and 8-4 (general vs. correction-aware) phrases respectively — large enough that a real back-and-forth conversation doesn't feel like it's repeating a single canned line (an earlier version hardcoded one follow-up question; fixed after live testing surfaced it). Its accuracy on this scope is continuously checked by the automated evaluation framework (`app/evaluation/`, see README).
- **`factory.py::get_llm_provider()`** — selects by `LLM_PROVIDER` env var, falling back to mock with a logged warning if `anthropic`/`openai` is selected but no key is present.

Switching providers is a config change, not a code change.

## Model routing / cost optimization (section 42)

`ModelTier.FAST` vs `ModelTier.STRONG`, set per LLM call:

- **STRONG**: `conversation_agent` only — the one output the user reads directly.
- **FAST**: error analysis, adaptation decision, teaching strategy, practice generation, recommendation phrasing, assessment question generation.

Combined with the graph's routine/significant routing (see [AGENTS.md](AGENTS.md)), a typical error-free conversational turn makes exactly one LLM call (the conversation agent), not seven.

`LLMUsage` (provider, model, input/output tokens) is captured on every call and appended to `TutorState["usage_log"]`, then persisted as real `AIUsageLog` rows in `persist_learning_event` (agent-graph calls) or via `app/services/ai_usage_service.py::log()` (calls made outside the graph — practice generation, assessment question generation, recommendation phrasing, background memory summarization). `app/services/usage_cost.py` estimates a USD cost from a small per-model pricing table. This backs the real, live admin AI-usage dashboard (`GET /api/v1/analytics/admin/ai-usage`, `/admin` page) — total calls/tokens/cost, breakdown by model and by node, daily cost trend.

## Prompt architecture (section 39)

One file per agent under `app/ai/prompts/`, each a pure function building `list[dict]` messages — no giant inline prompt strings scattered through business logic. `PROMPT_VERSION` in `base.py` is the version-tracking hook.

## Safety (section 43)

- `SAFETY_PREAMBLE` + `wrap_learner_message()`: learner-authored text is wrapped in `<learner_message>` tags with explicit instructions that it is untrusted content to analyze, never instructions to follow — mitigates prompt injection and system-prompt-extraction attempts.
- The system prompt is never echoed back to the client; only structured decision fields are exposed (see `AgentDecision` / "Why this lesson?").
- Agents never execute LLM-generated code or LLM-generated SQL. Database writes happen through typed SQLAlchemy models with parameterized queries; there is no code path where model output becomes a query string.
- File/audio uploads are size-capped (`app/api/v1/voice.py::MAX_AUDIO_BYTES`, 15MB).

## Memory (sections 14, 120)

Two tables per fact: `LearnerMemory` (the human-readable structured statement — e.g. *"User frequently confuses present perfect and simple past"*, never a raw chat dump) and `SemanticMemory` (its embedding, for retrieval by meaning via pgvector cosine distance — see [DATABASE.md](DATABASE.md#pgvector-note)). Retrieval (`retrieve_relevant_memories`) pulls the top-5 most relevant memories per turn; the full conversation history is never dumped into a prompt — only the last 8 turns plus the retrieved memory statements.

The **background summarization pass** (section 8/120) is a real, working Celery job: `app/tasks/jobs.py::summarize_recent_learner_activity` groups the last 24h of `LearnerError` activity per learner, calls `build_learner_model_summary_prompt` with a **STRONG**-tier model (this is exactly the kind of higher-value, non-latency-sensitive synthesis call that justifies the stronger/pricier model — see section 42), and writes the resulting `LearnerMemoryBatch` statements via `store_memory()`. Verified end-to-end during development: ran it directly against the live DB and confirmed real `LearnerMemory` rows were created, not placeholders.

## Content validation / anti-repetition (sections 88-90)

Generated practice questions are content-hash fingerprinted (`app/services/practice_service.py::_fingerprint`) against the learner's existing question set before being served, so near-duplicate exercises aren't repeated. `PracticeQuestion.validated` is a hook for a future automated content-quality pass (grammar/ambiguity/duplicate checks) before an exercise is served.
