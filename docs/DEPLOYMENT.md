# Deployment

## Docker Compose (the supported path)

```bash
cp apps/api/.env.example apps/api/.env   # edit JWT_SECRET at minimum
docker compose up --build
```

Services: `postgres` (pgvector-enabled image), `redis`, `api` (runs `alembic upgrade head` then `uvicorn` on container start), `worker` (Celery), `web` (Next.js production build). `pgadmin` is available under the `tools` profile: `docker compose --profile tools up`.

**Background jobs**: the `worker` service runs Celery workers but not the periodic scheduler — add a `beat` service (`command: celery -A app.tasks.celery_app beat --loglevel=info`) or run the worker with `-B` for a combined single-instance dev/demo setup, or the four real jobs (recommendation refresh, due-review reminders, memory summarization, stale-session cleanup — see `app/tasks/jobs.py`) will only ever run when triggered manually.

## Production checklist

- [ ] Set a strong, random `JWT_SECRET` (never the dev default).
- [ ] Set `ENV=production`, `DEBUG=false` (also enables the `Strict-Transport-Security` header — see SECURITY.md).
- [ ] Point `DATABASE_URL` / `REDIS_URL` at managed instances; the Postgres instance **must** support the `vector` extension (any managed Postgres with pgvector, e.g. RDS with the extension enabled, Supabase, Neon, or self-hosted `pgvector/pgvector`).
- [ ] Set `LLM_PROVIDER=anthropic` (or `openai`) with a real `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` — the mock provider is for local dev only, never production.
- [ ] Set `CORS_ORIGINS` to the real frontend origin(s) only.
- [x] Rate limiting is already wired up (`app/core/rate_limit.py`, Redis-backed, fails open) on auth/chat/practice/voice endpoints — tune the per-endpoint limits in each router if your traffic profile differs from the defaults.
- [ ] Configure `SENTRY_DSN` for error tracking if desired.
- [ ] Add a `beat` service/process for the Celery periodic schedule (see above) if you want background jobs to run automatically rather than only on manual/API trigger.
- [ ] Point your load balancer / orchestrator's readiness probe at `GET /health/ready` (checks DB + Redis) and liveness probe at `GET /health` (no dependency checks, always fast).
- [ ] Run `alembic upgrade head` as a release step, not implicitly on every container start in a multi-replica deployment (the docker-compose `command` does this for convenience in a single-instance dev/demo setup only).

## Scaling notes (section 107 — designed for, not implemented)

- `User.organization_id` / `User.teacher_id` are present but nullable — the schema doesn't need a migration to support future org/teacher features, just new endpoints.
- `Subscription.ai_tokens_used_month` / `voice_minutes_used_month` are present for future usage-limit enforcement; nothing currently increments them.
- The agent graph is stateless per-request (a fresh graph is compiled and bound to that request's DB session), so horizontal scaling of the API process is straightforward — there's no in-process session affinity requirement.

## CI

`.github/workflows/ci.yml` runs on every push/PR to `main`: backend lint (ruff) + migrations against a real Postgres service container + pytest; frontend typecheck + lint + vitest + production build; then Docker image builds for both. No deploy step is included — wire one in for your actual target (Fly.io, Railway, ECS, etc.) once you have one.
