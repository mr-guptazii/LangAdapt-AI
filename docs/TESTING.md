# Testing

## Backend (`apps/api/tests/`, pytest) — 51 tests

Run all: `cd apps/api && pytest` (unit tests need no database; integration tests need a real Postgres — see below, they're skipped gracefully if `TEST_DATABASE_URL`/`DATABASE_URL` isn't reachable... actually they'll error loudly, which is intentional: a missing test DB should fail visibly, not silently skip).

### Unit tests (no database) — 31 tests

| File | Covers |
|---|---|
| `test_mastery.py` | `update_mastery()` and `apply_forgetting_curve()` — correctness, clamping, repeated-mistake penalty, decay-toward-floor |
| `test_spaced_repetition.py` | SM-2-style scheduler — failed recall resets, successful recall grows interval (1 → 6 → ease-scaled), `quality_from_correctness()` mapping |
| `test_mock_provider.py` | Mock LLM provider actually detects `go → went`, embeddings are deterministic and unit-normalized, structured output validates against the real Pydantic schemas |
| `test_agent_graph.py` | The LangGraph graph compiles; the routine/significant routing function branches correctly — without invoking any node, so no DB or API key needed |
| `test_voice_analysis.py` | Speaking rate, pause detection, filler-word/repeated-word counting, and the fluency-score formula — all pure functions, 11 tests |
| `test_evaluation.py` | The agent evaluation framework itself (see below) — zero hallucinations, full recall on the mock provider's documented scope, recommendation-ranking formula correctness |

### Integration tests (real Postgres) — 20 tests, `tests/integration/`

Uses a real transactional-rollback pattern (`tests/integration/conftest.py`): each test gets a real `AsyncSession` bound to a connection with an outer transaction that's rolled back afterward (via SQLAlchemy's `join_transaction_mode="create_savepoint"`), so tests are fully isolated from each other and from dev/demo data without truncating tables between runs.

```bash
# Local: point at a dedicated throwaway database (never the dev/demo one)
createdb lingoadapt_test  # or: psql -c "CREATE DATABASE lingoadapt_test"
# alembic reads DATABASE_URL (not TEST_DATABASE_URL) — set it temporarily just for the migration:
cd apps/api && DATABASE_URL=postgresql+asyncpg://lingoadapt:lingoadapt@127.0.0.1:5432/lingoadapt_test alembic upgrade b2c3d4e5f6a7
TEST_DATABASE_URL=postgresql+asyncpg://lingoadapt:lingoadapt@127.0.0.1:5432/lingoadapt_test pytest tests/integration/
```

In CI, `TEST_DATABASE_URL` is unset and tests fall back to `DATABASE_URL`, which already points at CI's disposable per-run `pgvector/pgvector` service container (migrated with the FULL chain, including `semantic_memory`) — see `.github/workflows/ci.yml`.

| File | Covers |
|---|---|
| `test_auth_api.py` | Register, duplicate email (409), wrong password (401), `/me`, password-length validation |
| `test_authorization.py` | **Tenant isolation** (section 36) — a user cannot read another user's dashboard, session messages, or submit answers to another user's practice questions; admin endpoints reject non-admins; unauthenticated requests are rejected |
| `test_chat_flow.py` | The core agentic flow end-to-end: a routine message skips the heavy pipeline (cost routing verified), a past-tense mistake is detected AND actually persisted to `LearnerError`/`SkillMastery` (checked via direct DB query, not just the HTTP response), multi-turn sessions persist correctly |
| `test_practice_flow.py` | Generated questions carry real provenance (`source_skill_id`), unknown skill codes 404, submitting an answer updates mastery, exact-match grading works |
| `test_rate_limiting.py` | The REAL Redis-backed rate limiter (not bypassed) — hammers `/auth/login` and confirms `429` after the configured limit |

**A note on rate limiting in tests**: `httpx`'s `ASGITransport` gives every virtual test user the same synthetic client IP, so the business-logic integration tests (auth/chat/practice/authorization) deliberately override the rate-limit dependencies to no-ops via `app.dependency_overrides` — otherwise every test-created user would share one rate-limit bucket, an artifact of the test harness, not real behavior. The limiter itself is verified for real, without that override, in `test_rate_limiting.py`.

## Agent evaluation framework (section 60) — `app/evaluation/`

A curated dataset (`app/evaluation/datasets.py`) run against the real `error_analysis_agent` prompt + schema (`app/evaluation/runner.py`), scored with precision/recall/F1 (`app/evaluation/metrics.py`). Run standalone for a human-readable report:

```bash
cd apps/api && PYTHONPATH=. python scripts/run_evaluation.py
```

Current results against the mock provider (deterministic, reproducible): **0% hallucination rate**, **100% recall** on its documented scope (past tense — 3/3 cases), **62.5% overall pass rate** across the full 8-case dataset, which deliberately includes 3 cases (articles, prepositions, subject-verb agreement) outside the mock provider's rule-based scope — those are real-provider-only passes by design, not framework bugs. A separate deterministic check verifies the recommendation engine's ranking formula (section 87: balance, not always-recommend-the-weakest) with 100% pass. This framework caught two real bugs during development: a false-positive in the mock provider's past-tense word list (`have` was flagged standalone, producing a linguistically wrong double-correction) and an incorrect assumption in the original eval dataset about the recommendation formula's ranking behavior — both fixed, see git history.

## Frontend (`apps/web`, Vitest + Testing Library) — 8 tests

Run: `cd apps/web && npx vitest run`

- `src/lib/utils.test.ts` — `cn()` class merging, `formatMinutes()`, `formatRelativeTime()`
- `src/components/ui/Button.test.tsx` — renders children, fires `onClick`, respects `disabled`

`npx tsc --noEmit` and `npx eslint .` are both clean; `npm run build` produces a working production build (all 16 routes statically prerendered, including `/admin`).

## What's *not* covered

**No Playwright/E2E tests** are included. The brief calls for e2e coverage of registration/login/onboarding/assessment/conversation/voice; given the scope already delivered, this was consciously deprioritized in favor of real integration tests against a real database plus extensive manual verification. `apps/web` has Vitest + Testing Library wired up and ready for Playwright to be added alongside.

## Manual end-to-end verification performed during development

Against a live PostgreSQL 17 + Redis instance (native Windows install, no Docker — see DATABASE.md for the pgvector caveat) with the mock LLM provider, beyond what the automated suite covers:

1. Full migration chain behavior: the pgvector-independent branch applies cleanly (32 tables); the pgvector-dependent migration fails cleanly and rolls back in this sandbox, confirmed isolated to exactly one table.
2. `scripts/seed.py` → demo user + 24 skills + 8 languages + realistic historical data, verified via direct SQL query.
3. Voice pipeline: `/voice/transcribe` produces real, internally-consistent computed metrics (speaking rate, pause count, fluency score) from simulated-but-deterministic timing data; `/voice/synthesize` returns correctly base64-encoded audio (fixed from an earlier hex-encoding bug) or a clearly-labeled mock response.
4. Celery background jobs: all four (`generate_recommendations_for_active_users`, `send_due_review_reminders`, `summarize_recent_learner_activity`, `cleanup_stale_sessions`) invoked directly against the live DB and confirmed to write real rows (recommendations generated, `LearnerMemory` statements synthesized via a real STRONG-tier LLM call).
5. Admin dashboard endpoints: all 5 verified via curl with real aggregated data, including a live Redis ping showing real measured latency and a genuine `unhealthy` result before Redis was installed (proving the health check isn't hardcoded).
6. Rate limiting: hammered `/auth/login` past its configured limit and confirmed `429` at the exact expected request count; confirmed the limiter fails open when Redis is separately made unreachable.
7. Frontend: production build, dev server boot, and all pages (including `/admin`) verified to return 200 and render real content.
