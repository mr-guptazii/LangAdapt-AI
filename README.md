# LingoAdapt AI

**An AI language tutor that adapts to how you actually learn.**

LingoAdapt is a personalized, agentic AI language-learning platform. Instead of a single chatbot prompt, every learner turn runs through a deterministic **LangGraph** agent pipeline that observes behavior, detects and classifies mistakes, updates a persistent learner model, decides how to adapt difficulty and teaching strategy, and only then generates a response — storing structured long-term memory along the way.

See [ARCHITECTURE.md](docs/ARCHITECTURE.md), [AGENTS.md](docs/AGENTS.md), [DATABASE.md](docs/DATABASE.md), [AI_SYSTEM.md](docs/AI_SYSTEM.md), [VOICE.md](docs/VOICE.md), [SECURITY.md](docs/SECURITY.md), [TESTING.md](docs/TESTING.md), and [DEPLOYMENT.md](docs/DEPLOYMENT.md) for deep dives.

## What's actually implemented

This is a working full-stack application, not a mockup — every page below reads and writes real data through the real backend, and every claim in this table was verified live against a real PostgreSQL + Redis instance during development (see TESTING.md for the verification log).

| Area | Status |
|---|---|
| Auth (register/login/JWT) | Real, bcrypt + JWT, Redis-backed rate limiting on register/login |
| Onboarding + adaptive placement assessment | Real, IRT-style difficulty adjustment |
| LangGraph agent pipeline (12 nodes) | Real, with intelligent routing to skip expensive nodes on routine turns |
| Error detection, mastery scoring, spaced repetition | Real, deterministic algorithms (documented in `app/learning/`) |
| Long-term structured memory + pgvector semantic retrieval | Real (requires the `vector` Postgres extension — see note below) |
| Practice generation with provenance (`source_error_id`) | Real |
| Recommendation engine (deterministic ranking + LLM phrasing) | Real, **automatically evaluated** (see Agent evaluation below) |
| "Why this lesson?" agent decision trace | Real, structured (no exposed chain-of-thought) |
| Dashboard / Progress / Mistakes / Vocabulary pages | Real, all backend-driven |
| **Voice pipeline** | Real STT/TTS provider interfaces; **real, deterministically-computed** speaking rate / pauses / filler words / fluency score (from Whisper segment timestamps when `STT_PROVIDER=openai_whisper`, or from consistent simulated timing in mock mode — see VOICE.md); frontend does real microphone capture (`MediaRecorder`) + live waveform + TTS playback with browser-speech fallback |
| **Pronunciation scoring** | Estimate-only by design (no phoneme-level provider wired up) — always labeled `is_estimated: true`, never presented as precise |
| **Analytics events** | Real event log (`AnalyticsEvent`) emitted at 14 real trigger points across the app (chat, practice, vocabulary, assessment, voice, sessions) — powers the Progress page's activity chart and the admin dashboard |
| **AI usage / cost tracking** | Real (`AIUsageLog`) — every LLM call, from the agent graph and from practice/assessment/recommendation generation, is logged with tokens and an estimated cost |
| **Background jobs (Celery)** | Real — recommendation refresh, due-review reminders, learner-memory summarization (the background LLM synthesis pass), and stale-session cleanup, all run against real data and verified end-to-end |
| **Admin dashboard** | Real — user/session/retention metrics, AI usage & cost breakdown, common-errors-across-all-users, system health (live DB + Redis ping) |
| **Production hardening** | Redis-backed rate limiting (fails open), security headers, `/health` (liveness) + `/health/ready` (readiness, real dependency checks) |
| Payments / subscriptions | Schema only, no payment provider wired up |
| i18n UI | Not implemented; the *learning engine* is language-agnostic (see `app/learning/languages/`) |

## Quick start

### Option A — Docker Compose (recommended)

```bash
cp apps/api/.env.example apps/api/.env
docker compose up --build
# API:        http://localhost:8000  (docs at /docs)
# Web:        http://localhost:3000
```

The `pgvector/pgvector:pg16` Postgres image bundles the `vector` extension, so both migrations succeed out of the box and semantic memory retrieval works fully. The `worker` service runs the real Celery background jobs (`app/tasks/`); add a `beat` service (or run `celery ... worker -B`) to actually fire them on their periodic schedule — see `app/tasks/celery_app.py`.

### Option B — Native (no Docker)

Requires PostgreSQL 16+ and Redis running locally.

```bash
# Backend
cd apps/api
python -m venv .venv && .venv/Scripts/activate  # or source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit DATABASE_URL/REDIS_URL if needed
alembic upgrade head
PYTHONPATH=. python scripts/seed.py
uvicorn app.main:app --reload

# Worker (separate terminal, optional — background jobs)
cd apps/api && celery -A app.tasks.celery_app worker --loglevel=info

# Frontend (separate terminal)
cd apps/web
npm install
cp .env.local.example .env.local
npm run dev
```

> **pgvector on native Windows Postgres**: the community `vector` extension has no official prebuilt Windows binary — it must be compiled with an MSVC toolchain. The initial-schema migration (30 tables, plus the `analytics_and_usage` branch — 32 tables total) runs fine without it; the follow-up `semantic_memory` migration needs it. Everything degrades gracefully without it (see [DATABASE.md](docs/DATABASE.md#pgvector-note)) — semantic memory retrieval just returns `[]` until the extension is available. This exact setup (native Windows Postgres 17 + native Redis, no Docker) is what this build was developed and verified against. Docker Compose sidesteps the pgvector gap entirely.

Log in with the seeded demo account: **demo@lingoadapt.ai / demo1234** (a B1-level learner with realistic past-tense/article/preposition weaknesses and vocabulary strength already populated).

## Tech stack

- **Backend**: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic, LangGraph, PostgreSQL + pgvector, Redis, Celery
- **Frontend**: Next.js 15.5 (App Router), TypeScript (strict), Tailwind CSS, Framer Motion, Recharts, Zustand
- **AI**: Provider-agnostic (`app/ai/providers/`) — Anthropic, OpenAI-compatible, or a dependency-free mock provider used automatically when no API key is configured

## How agents work (short version)

```
user message
  → load_learner_context → retrieve_relevant_memory
  → conversation_agent → error_analysis_agent
  → [routing: skip the next 3 nodes on routine, error-free turns]
  → learner_model_agent → adaptation_agent → teaching_strategy_agent → practice_or_response_agent
  → generate_response
  → persist_learning_event (also logs AI usage + analytics events) → update_memory → update_recommendations
```

Full detail, including the routing/cost-optimization rationale, is in [AGENTS.md](docs/AGENTS.md).

## Agent evaluation (section 60)

`app/evaluation/` runs a curated dataset against the real `error_analysis_agent` prompt/schema and a deterministic check of the recommendation-ranking formula. Run it yourself:

```bash
cd apps/api && PYTHONPATH=. python scripts/run_evaluation.py
```

Also runs automatically in the test suite (`tests/test_evaluation.py`) and CI. The mock provider scores **0% hallucination rate** and **100% recall on its documented scope** (past tense) — the framework honestly reports partial recall on categories outside that scope (articles, prepositions, subject-verb agreement), which is exactly the expected, correct result for a rule-based stand-in, not a framework bug.

## How personalization works

The learner's `LearningPreference` row (conversation vs. quiz affinity, correction style, challenge tolerance, explanation length, interests) is read on every conversational turn and injected into the conversation/teaching-strategy prompts — it isn't cosmetic. It's updated both explicitly (onboarding/settings) and, in a production build, by observed engagement (the `evidence` JSON column is designed to carry that trail).

## How memory works

Two tiers: short-term (recent conversation turns passed to the LLM, capped rather than dumped wholesale) and long-term (`LearnerMemory` — structured facts like *"User frequently confuses present perfect and simple past"* — each backed by a `SemanticMemory` embedding for top-K retrieval by meaning, not just recency, PLUS a real background Celery job that periodically synthesizes recent errors into new memory statements using a STRONG-tier model call). See [AI_SYSTEM.md](docs/AI_SYSTEM.md).

## Environment variables

See [apps/api/.env.example](apps/api/.env.example) and [apps/web/.env.local.example](apps/web/.env.local.example). The app boots and is fully demoable with zero API keys via the mock LLM/STT/TTS/embedding providers.

## Database

32 tables across users/learner-model/curriculum/practice/assessment/voice/memory/recommendations/analytics/system domains. Migrations are branched so the one pgvector-dependent table (`semantic_memories`) is isolated from the other 31 — see [DATABASE.md](docs/DATABASE.md).

## Testing

```bash
make test          # both suites
make test-api       # pytest — mastery/SRS math, mock provider, agent-graph routing, agent evaluation, plus real DB integration tests (auth/authorization/chat/practice/rate-limiting)
make test-web        # vitest — utils + component tests
```

51 backend tests (27 unit + 20 integration + 4 evaluation), 8 frontend tests, all passing. See [TESTING.md](docs/TESTING.md) for exactly what's covered, including the pattern used for isolated, real-Postgres integration tests (SAVEPOINT-per-test rollback) and what still isn't included (Playwright e2e).

## Known limitations

- **Pronunciation**: no phoneme-level provider integrated (no production service was wired up); `PronunciationScore.is_estimated` is always `true` until one is. Speaking rate, pauses, filler words, and fluency ARE real, computed metrics (not estimates) — see VOICE.md for the distinction.
- **Payments**: `Subscription` model exists; no Stripe/payment integration.
- **i18n**: interface is English-only; the learning *engine* itself is language-abstracted (`app/learning/languages/<code>/`) with only `en` populated.
- **E2E tests**: not included (unit + integration + evaluation only) — see TESTING.md.
- **CI**: lint/typecheck/test/coverage/security-scan/build wired in GitHub Actions; no deploy step (no target environment specified).
- **Dependency vulnerabilities**: two accepted, documented, low-real-risk findings remain after upgrading Next.js to close a large batch of real CVEs — see SECURITY.md for the specifics and rationale.
- **Celery beat**: the periodic schedule is defined (`app/tasks/celery_app.py`) but no `beat` process ships in `docker-compose.yml` by default — add one (or run `-B`) to have jobs fire on their own schedule rather than only via manual/API trigger.

## License

Demo/portfolio project — no license file included; treat as all-rights-reserved unless you add one.
