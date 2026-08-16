# CLAUDE.md

Working notes for anyone (human or Claude) picking up LingoAdapt AI. This file
tracks what's real, what's not, why key decisions were made, and what's next —
not a feature list restating the code, but the context you'd otherwise have to
re-derive by reading every file.

## What this is

An agentic language-tutoring platform: FastAPI + LangGraph backend, Next.js 15
frontend, PostgreSQL + pgvector, Redis, Celery. A stateful multi-agent graph
(conversation, error analysis, learner modeling, adaptation, teaching strategy,
practice generation) drives a personalized tutoring loop, backed by a voice
pipeline, adaptive placement assessment, and spaced repetition.

Deployed: Render (API + worker + managed Postgres/Redis) and Vercel (frontend).
LLM + STT currently run on Groq (`llama-3.1-8b-instant` FAST / `llama-3.3-70b-versatile`
STRONG, `whisper-large-v3-turbo`) via the OpenAI-compatible provider abstraction.

## Completed and verified real (as of 2026-08-16)

Confirmed by a 6-agent source-level audit against 56 spec requirements, then by
implementation + tests + a live run against the real Groq provider — not
assumed from file existence.

- **Core loop**: conversation → error analysis → learner model → mastery →
  personalized practice → progress, all backed by real DB writes (verified
  end-to-end by `tests/integration/test_error_to_practice_loop.py`, which
  reproduces the exact "Yesterday I go to college and buy some food." scenario).
- **Personalization actually diverges per learner** — verified live against
  real Groq output, not just unit-tested: `ai_personality`, correction style,
  and explanation length each measurably change the tutor's conversational
  output; weak-skill data measurably changes practice targeting and
  recommendations. See `app/services/demo_learners.py` (Learner A: B1, strong
  vocab, weak past tense, prefers conversation, short explanations; Learner B:
  B1, strong grammar, weak vocab, prefers quizzes, detailed explanations) and
  `tests/integration/test_personalization_divergence.py`.
- **Adaptive placement assessment**: real IRT-lite scoring, hardened against
  four separate live-observed prompt-quality failure modes (incomplete
  passages, off-topic questions, ambiguous multi-answer options, missing
  question sentences) across all 6 skill areas, with a STRONG-tier structural
  retry when FAST-tier output fails validation.
- **Voice**: real mic capture → real Groq Whisper transcription → real
  deterministic speech-metric math (rate/pauses/fillers/fluency). TTS has a
  complete, ready-to-activate provider, currently mock only for lack of a
  verified TTS-capable endpoint. Pronunciation is honestly mocked (confidence-
  anchored estimate, `is_estimated: true` surfaced everywhere) — no real
  phoneme-level provider exists to switch to yet.
- **Memory**: pgvector read/write is real; embeddings are now a real
  deterministic lexical (hashing-trick) provider by default (`EMBEDDING_PROVIDER=hashing`),
  not the previous unconditional random-noise mock.
- **Mastery, spaced repetition (SM-2-style), recommendation ranking,
  dashboard/progress/mistakes/vocabulary/practice pages**: all real,
  DB-backed, no fabricated numbers.
- **Security fundamentals**: JWT auth, bcrypt, real rate limiting (Redis
  fixed-window), real tenant isolation, CORS allow-list — all tested.
- **CI**: real gated pipeline (lint, pip-audit, migrations, tests, coverage,
  frontend typecheck/lint/build, Docker build) on every push.

## Known incomplete / honestly mocked (do not claim these are done)

- **Forgot-password**: pure frontend mock (`setSent(true)`, no backend call at
  all). No backend route, no reset-token model, no email sending anywhere in
  the codebase.
- **Data export / account deletion**: export claims "emailed to you shortly"
  but no export file is ever generated and no email integration exists
  anywhere. Deletion only flips `is_active = False` — not real erasure.
- **`STORE_RAW_AUDIO` toggle**: exists as a real per-user setting but controls
  nothing — no code path ever writes raw audio to storage regardless of the
  toggle's value.
- **Scenario engine**: schema column (`LearningSession.scenario`) and prompt
  parameter exist; nothing ever sets or reads them. No roleplay template
  catalog exists.
- **Interest-based personalization**: `interests`/`preferred_topics` are
  captured at onboarding and displayed in settings, never read by any
  conversation/practice/recommendation logic.
- **Daily learning plan**: does not exist. The closest feature is the ranked
  top-3 recommendation list (`recommendation_service.py`), which is not a
  day-grouped plan with completion tracking.
- **Notifications**: real DB rows are written (`send_due_review_reminders`
  Celery job), but there is no delivery channel (no email/push/SMTP anywhere)
  and no frontend notification UI at all.
- **Celery beat**: the periodic job schedule is defined
  (`app/tasks/celery_app.py`) but no `beat` process runs in `docker-compose.yml`
  or `render.yaml` — recommendation refresh, review reminders, and memory
  summarization only fire if triggered manually.
- **`get_curriculum()`**: dead code — its own docstring claims the
  adaptation/recommendation engines consult it; they don't.
- **E2E tests**: none (Playwright/Cypress). Documented as a deliberate
  deprioritization in `docs/TESTING.md`, not an oversight.

## Architectural decisions worth knowing

- **LLM provider abstraction** (`app/ai/providers/`): everything goes through
  `LLMProvider.structured()` with forced tool-calling — never regex-parsed
  free text for anything that drives a decision. Swapping providers
  (Anthropic / any OpenAI-compatible backend via `OPENAI_BASE_URL`) is a
  config change. Currently Groq, chosen over Gemini specifically because
  Gemini's free tier is a hard 20 req/day ceiling that broke under real usage;
  Groq's is a genuine recurring daily quota.
- **Cost-tiered agent graph**: a routine, error-free conversation turn skips
  four LLM-calling nodes (`learner_model_agent` onward) via conditional
  routing in `graph.py` — this is deliberate, not a missing feature.
- **Embeddings** (`app/ai/providers/lexical_provider.py`): a signed
  hashing-trick bag-of-words vector, not a neural embedding. Chosen over a
  local sentence-transformers model because torch's memory footprint would
  likely OOM the same memory-constrained Render instance that already needed
  `--pool=solo` on Celery to avoid exactly that. It's real (content-sensitive
  under cosine similarity) but explicitly not claimed to understand synonyms
  or paraphrase — see the file's docstring for the honest scope.
- **Test database**: `TEST_DATABASE_URL` falls back to the real local
  `DATABASE_URL` when unset — tests run against the actual dev Postgres, not
  an isolated instance. This caused real, confusing `MultipleResultsFound`
  failures (fixed 2026-08-16: `seeded_skill` fixture and two test queries were
  blindly unscoped/non-idempotent against a DB that already had committed
  demo data from `scripts/seed.py`). If you add a fixture that inserts
  reference data, look it up first — don't assume you're starting from empty.
- **Adaptation feedback loop**: `difficulty_decision` is computed, logged to
  `AgentDecision`, AND applied to `LearnerProfile.current_difficulty` (fixed
  2026-08-16 — it was previously computed and returned to the client but
  never actually changed anything for future turns).
- **`personalization_enabled`** (privacy opt-out, `Profile` table): when
  false, `load_learner_context` substitutes default personality/interests
  before they ever reach agent state — a disabled learner's real traits never
  reach an LLM prompt even indirectly.

## Known issues to watch

- `TeachingStrategyDecision`'s outcome-tracking table (`app/models/agent.py`
  `TeachingStrategy`, distinct from `AgentDecision`) is defined but never
  instantiated anywhere — dead code, not wired to anything.
- `teaching_strategy_agent`'s effect on the SAME turn's response text is
  limited: it can gate whether a practice nudge is recommended
  (`practice_or_response_agent`), but `generate_response` only reads
  `conversation_output`, produced earlier in the graph — the strategy can't
  retroactively change what the conversation agent already said this turn.
- `LearnerError.weakness_score` only ever increases (new mistakes) — nothing
  decreases it after successful practice, so the recommendation engine's
  "recent_mistake" signal doesn't reflect improved performance on its own
  (spaced-repetition scheduling on `SkillMastery` does move correctly, which
  is a real signal, just a different one).
- Render's blueprint (`render.yaml`) doesn't expose `STT_PROVIDER`,
  `TTS_PROVIDER`, `PRONUNCIATION_PROVIDER`, or `EMBEDDING_PROVIDER` as
  configurable env vars — they default to `mock`/`hashing` in every deployed
  environment unless an operator adds them manually outside the blueprint.

## Exact next steps (priority order)

1. **P1**: wire `interests` into conversation topic / practice content
   selection; give `teaching_strategy_agent` real influence over the same-turn
   response (likely requires reordering the graph or feeding its decision back
   into `conversation_agent`); build a real forgot-password flow; make data
   export/deletion honest (real export endpoint, real erasure or an honest UI
   caveat); add a Celery `beat` process to `docker-compose.yml`/`render.yaml`
   so the periodic schedule actually fires.
2. **P2**: nothing code-blocking — STT is real and live; TTS just needs a
   verified-working endpoint + `TTS_PROVIDER=openai_tts` in Render's env vars;
   pronunciation needs a real credentialed provider (Azure Speech or similar)
   written from scratch when/if credentials exist.
3. **P3**: wire Sentry (`SENTRY_DSN` is configured but `sentry_sdk.init()` is
   never called); expand structlog coverage past the current 7 files; add a
   refresh-token endpoint; add `STT_PROVIDER`/`TTS_PROVIDER`/`EMBEDDING_PROVIDER`
   to `render.yaml` so they're configurable without going outside the
   blueprint.
4. **P4**: a real daily learning plan feature; Playwright E2E coverage; a
   notification delivery channel (email/push) once a provider is chosen;
   remove or wire `get_curriculum()`.

## Commands

```bash
# Backend (from apps/api, venv active)
python -m pytest tests/ -q                    # full suite
python -m ruff check .                         # lint
python -m mypy app/ --ignore-missing-imports   # typecheck
python -m alembic upgrade b2c3d4e5f6a7          # migrate (pgvector-independent branch — use `head` if pgvector is installed)
python -m scripts.seed                          # seed languages/curriculum/demo account
python -m scripts.seed_demo_learners             # seed the two personalization-test learners
python -m uvicorn app.main:app --reload         # run locally

# Frontend (from apps/web)
npx tsc --noEmit && npx eslint . && npm run build
```

## Environment variables that matter

- `LLM_PROVIDER=openai` + `OPENAI_BASE_URL=https://api.groq.com/openai/v1` +
  `OPENAI_API_KEY` + `OPENAI_MODEL_FAST=llama-3.1-8b-instant` +
  `OPENAI_MODEL_STRONG=llama-3.3-70b-versatile` — real conversation/error-analysis/
  adaptation/teaching-strategy/practice/recommendation generation.
- `STT_PROVIDER=openai_whisper` + `STT_MODEL=whisper-large-v3-turbo` — real
  transcription (same Groq key/base URL).
- `EMBEDDING_PROVIDER=hashing` (default) — real, no key needed.
- Everything else (`TTS_PROVIDER`, `PRONUNCIATION_PROVIDER`) stays `mock`
  until a verified credential/endpoint exists — see "Known incomplete" above.
