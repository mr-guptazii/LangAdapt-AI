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
  verified TTS-capable endpoint — the frontend visibly labels this ("device
  voice") rather than presenting the browser fallback as production AI voice.
  Pronunciation shows **no score at all**, not even a labeled estimate — a
  "Pronunciation analysis coming soon" message — since no real phoneme-level
  provider exists yet (fixed 2026-08-16: previously fabricated a
  confidence-anchored estimate).
- **Memory**: pgvector read/write is real; embeddings are a real deterministic
  lexical (hashing-trick) provider by default (`EMBEDDING_PROVIDER=hashing`),
  not random noise. **Cross-user isolation is explicitly tested**
  (`tests/integration/test_memory_isolation.py`) — memories, conversations,
  errors, vocabulary, and AI decision traces are proven unreachable across
  users, including a direct call to the retrieval function bypassing the HTTP
  layer entirely.
- **Password reset**: a real, secure token-based flow (`app/services/auth_service.py`
  `request_password_reset`/`reset_password`) — SHA-256-hashed tokens, 30-minute
  expiry, single-use, no user-enumeration leak. No email transport is wired up
  yet, so the frontend is honest about that limit (self-service email delivery
  isn't live; contact support) rather than claiming a link was sent.
- **Data export/deletion**: `/settings/export` returns the caller's real data
  directly as a downloadable JSON file (no email needed). `/settings/account`
  performs real deletion — the `User` row is removed and every owned row
  cascades with it (learner profile, sessions, messages, errors, mastery,
  vocabulary, memories, recommendations); the audit trail survives with the
  actor reference cleared (`ON DELETE SET NULL`), not cascaded away.
- **Interests**: now read by the conversation prompt (natural topic/example
  hints) and the recommendation-phrasing prompt — previously captured at
  onboarding and never read anywhere.
- **Admin dashboard**: seeded demo/showcase accounts (`User.is_demo`) are
  excluded from every business metric (`total_users`, CEFR/language
  distribution, retention, common-errors) so they can never inflate what
  looks like real production usage.
- **Mastery, spaced repetition (SM-2-style), recommendation ranking,
  dashboard/progress/mistakes/vocabulary/practice pages**: all real,
  DB-backed, no fabricated numbers.
- **Security fundamentals**: JWT auth, bcrypt, real rate limiting (Redis
  fixed-window), real tenant isolation, CORS allow-list — all tested.
- **CI**: real gated pipeline (lint, pip-audit, migrations, tests, coverage,
  frontend typecheck/lint/build, Docker build) on every push.

## Known incomplete / honestly mocked (do not claim these are done)

- **`STORE_RAW_AUDIO` toggle**: exists as a real per-user setting but controls
  nothing — no code path ever writes raw audio to storage regardless of the
  toggle's value.
- **Scenario engine**: schema column (`LearningSession.scenario`) and prompt
  parameter exist; nothing ever sets or reads them. No roleplay template
  catalog exists.
- **Interests in practice generation**: wired into conversation and
  recommendations (see above), but practice-exercise content still targets
  weak skills only, not interests — a bigger prompt-design change than the
  additive hint used for the other two surfaces.
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
- **Pronunciation provider**: no real implementation exists to activate —
  would need to be written from scratch against a real credentialed API
  (Azure Speech or similar) when one is available.
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
- **Account deletion FK safety** (`app/models/system.py` `AuditLog.actor_user_id`,
  `app/models/user.py` `User.teacher_id`): both changed to `ON DELETE SET NULL`
  (migration `e5f6a7b8c9d0`) — without this, real account deletion would fail
  outright the moment an account had ever done anything audit-logged (which is
  every account, from registration onward).

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
- Migrations `d4e5f6a7b8c9` and `e5f6a7b8c9d0` chain after the pgvector-merge
  head (`c3d4e5f6a7b8`), so — like everything after that merge — they require
  the `vector` extension to apply via a plain `alembic upgrade head`, even
  though neither migration's own table needs it. Verified correct via
  `alembic upgrade ... --sql` (offline SQL generation) and by manually
  applying the equivalent DDL locally, since this dev machine's Postgres has
  no pgvector installed. Not an issue on Render (pgvector is already applied
  there) — see `test_memory_isolation.py`'s pgvector-dependent test, which
  skips cleanly in the same situation rather than failing.

## Exact next steps (priority order)

1. **P1**: wire `interests` into practice-generation content (conversation and
   recommendations already do this); give `teaching_strategy_agent` real
   influence over the same-turn response (likely requires reordering the graph
   or feeding its decision back into `conversation_agent`); add a Celery
   `beat` process to `docker-compose.yml`/`render.yaml` so the periodic
   schedule actually fires; wire up real email delivery so the password-reset
   flow becomes fully self-service.
2. **P2**: nothing code-blocking — STT is real and live; TTS just needs a
   verified-working endpoint + `TTS_PROVIDER=openai_tts` in Render's env vars
   (now exposed in `render.yaml`); pronunciation needs a real credentialed
   provider (Azure Speech or similar) written from scratch when/if
   credentials exist.
3. **P3**: wire Sentry (`SENTRY_DSN` is configured but `sentry_sdk.init()` is
   never called); expand structlog coverage past the current 7 files; add a
   refresh-token endpoint.
4. **P4**: a real daily learning plan feature; Playwright E2E coverage; a
   notification delivery channel (email/push) once a provider is chosen;
   remove or wire `get_curriculum()`.

## Commands

```bash
# Backend (from apps/api, venv active)
python -m pytest tests/ -q                    # full suite
python -m ruff check .                         # lint
python -m mypy app/ --ignore-missing-imports   # typecheck
python -m alembic upgrade head                  # migrate (requires pgvector — see "Known issues" above)
python -m scripts.seed                          # seed languages/curriculum/demo account
python -m scripts.seed_demo_learners             # seed the two personalization-test learners
python -m uvicorn app.main:app --reload         # run locally

# Frontend (from apps/web)
npx tsc --noEmit && npx eslint . && npm run build

# Docker (from repo root)
docker build -f infrastructure/docker/Dockerfile.api -t lingoadapt-api .
docker build -f infrastructure/docker/Dockerfile.worker -t lingoadapt-worker .
docker build -f infrastructure/docker/Dockerfile.web -t lingoadapt-web .

# Deploy: push to main triggers Render (API + worker, Docker rebuild + auto-migrate
# via entrypoint.sh) and Vercel (frontend) simultaneously. No separate deploy command.
```

## Environment variables that matter

- `LLM_PROVIDER=openai` + `OPENAI_BASE_URL=https://api.groq.com/openai/v1` +
  `OPENAI_API_KEY` + `OPENAI_MODEL_FAST=llama-3.1-8b-instant` +
  `OPENAI_MODEL_STRONG=llama-3.3-70b-versatile` — real conversation/error-analysis/
  adaptation/teaching-strategy/practice/recommendation generation.
- `STT_PROVIDER=openai_whisper` + `STT_MODEL=whisper-large-v3-turbo` — real
  transcription (same Groq key/base URL). Now exposed as configurable
  `render.yaml` blueprint vars (previously had to be added manually outside
  the blueprint).
- `EMBEDDING_PROVIDER=hashing` (default) — real, no key needed.
- `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET` — provisioned automatically by
  `render.yaml` (`fromDatabase`/`fromService`/`generateValue`), never
  hardcoded anywhere in the codebase.
- `CORS_ORIGINS` — must be the real deployed frontend origin (e.g.
  `["https://lang-adapt-ai.vercel.app"]`), set manually post-deploy since the
  Vercel URL isn't known at first Render deploy.
- `NEXT_PUBLIC_API_URL` (Vercel, build-time) — baked into the frontend bundle
  at build time, not runtime; changing it requires a fresh Vercel build, not
  just an env var update.
- Everything else (`TTS_PROVIDER`, `PRONUNCIATION_PROVIDER`) stays `mock`
  until a verified credential/endpoint exists — see "Known incomplete" above.
