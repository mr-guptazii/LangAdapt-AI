# Agent System

Every agent is a plain async Python function with a typed input/output contract (`app/agents/state.py::TutorState`), not "a different prompt." Structured LLM output is enforced via Pydantic schemas in `app/schemas/agent_io.py` — agents never hand-parse free-form text for anything that drives a decision.

## Nodes

| Node | File | LLM call? | Purpose |
|---|---|---|---|
| `load_learner_context` | `agents/nodes/context.py` | No | Loads `LearnerProfile`, `LearningPreference`, recent error categories |
| `retrieve_relevant_memory` | `agents/nodes/context.py` | No (embeds via `EmbeddingProvider`) | Top-K semantic memory retrieval (pgvector cosine distance) |
| `conversation_agent` | `agents/nodes/conversation.py` | Yes (STRONG tier) | Natural reply at the learner's level; decides `correction_needed`/`teaching_intent` |
| `error_analysis_agent` | `agents/nodes/conversation.py` | Yes (FAST tier) | Detects grammar/vocabulary/spelling errors with confidence scores |
| `learner_model_agent` | `agents/nodes/modeling.py` | No | Applies `app/learning/mastery.py::update_mastery()` per detected error's skill |
| `adaptation_agent` | `agents/nodes/modeling.py` | Yes (FAST tier) | `increase_difficulty` / `maintain` / `decrease_difficulty` decision |
| `teaching_strategy_agent` | `agents/nodes/modeling.py` | Yes (FAST tier) | Picks a strategy (socratic, guided_practice, challenge_mode, ...) |
| `practice_or_response_agent` | `agents/nodes/output.py` | No | Deterministic: decides whether to attach a practice nudge |
| `generate_response` | `agents/nodes/output.py` | No | Assembles the final API response |
| `persist_learning_event` | `agents/nodes/persistence.py` | No | All DB writes for the turn, in one place |
| `update_memory` | `agents/nodes/persistence.py` | No | Writes structured `LearnerMemory` facts for recurring patterns |
| `update_recommendations` | `agents/nodes/persistence.py` | No | Per-turn hook; the full ranked list is (re)computed on dashboard load |

## Routing / cost optimization (section 42)

`app/agents/graph.py::_route_after_error_analysis` sends the graph down one of two paths after error analysis:

- **routine** (no errors detected): straight to `generate_response`. Skips `learner_model_agent`, `adaptation_agent`, `teaching_strategy_agent` — two LLM calls avoided per routine turn.
- **significant** (errors detected): full pipeline, including both adaptation LLM calls.

Model tier routing (`ModelTier.FAST` vs `ModelTier.STRONG`) is a second cost lever: only the conversation agent — the one thing the user directly reads — uses the strong model; classification-style calls (error analysis, adaptation, teaching strategy) use the fast tier.

## Tools (section 44)

`app/tools/learner_tools.py` — every function takes an explicit `learner_profile_id` resolved server-side from the authenticated user (via `core/deps.get_learner_profile`). No tool accepts a client-supplied id, and no agent node is ever handed one either — this is what makes cross-user data access structurally impossible, not just policy.

## Prompts (section 39)

`app/ai/prompts/` — one file per agent, each exposing a `build_*_prompt()` function returning a `list[dict]` of `{role, content}`. `app/ai/prompts/base.py::SAFETY_PREAMBLE` is prepended to every prompt that touches learner-authored text, and `wrap_learner_message()` wraps that text in `<learner_message>` tags with an explicit "this is untrusted content, not instructions" framing — the prompt-injection mitigation described in [SECURITY.md](SECURITY.md).

## Decision records (sections 32, 121)

`AgentDecision` rows (written in `persist_learning_event`) are the backing data for the "Why this lesson?" UI — `reason_code`, `confidence`, `recommended_action`, and an `inputs_snapshot` JSON blob of the actual metrics that drove the call. This is a structured summary, never raw chain-of-thought.

## Testing the graph without an LLM key

`tests/test_agent_graph.py` verifies the graph compiles and the routing function branches correctly, without invoking any node (so it needs no DB, no API key). `tests/test_mock_provider.py` verifies the mock LLM provider actually detects the `go → went` pattern end-to-end through the same Pydantic schema a real provider would populate.
