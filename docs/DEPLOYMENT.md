# Deployment

## Vercel (frontend) + Render (backend) — the live deployment path

This is a two-platform split: Vercel for the Next.js frontend (best-in-class
Next.js hosting), Render for everything else (API, Celery worker, Postgres
with pgvector, Redis) via the committed `render.yaml` blueprint. Both steps
require your own login — an agent can prepare the code and configs but can't
complete an OAuth flow on your behalf.

### 1. Backend — Render

1. Push this repo to GitHub (already done if you're reading this from the deployed repo).
2. In the Render dashboard: **New → Blueprint**, select this repo. Render reads `render.yaml` at the repo root and provisions four resources: `lingoadapt-db` (Postgres, pgvector-enabled), `lingoadapt-redis` (Key Value), `lingoadapt-api` (web service), `lingoadapt-worker` (Celery worker).
3. You'll be prompted for the `sync: false` env vars during creation — at minimum decide `LLM_PROVIDER`:
   - `mock` — boots immediately, zero cost, zero setup (see AI_SYSTEM.md for what this means in practice).
   - `anthropic` + `ANTHROPIC_API_KEY` — real Claude.
   - `openai` + `OPENAI_API_KEY` (+ `OPENAI_BASE_URL`, `OPENAI_MODEL_FAST`, `OPENAI_MODEL_STRONG`) — real OpenAI, or any OpenAI-compatible backend (NVIDIA NIM, Gemini's compat endpoint, Groq, etc.) — see `.env.example` for exact per-backend values, and AI_SYSTEM.md for two real gotchas hit getting Gemini working (a token-budget floor for reasoning models, and a fallback for backends that don't reliably honor forced tool-calling).
4. `lingoadapt-api`'s `startCommand` runs `alembic upgrade head` before `uvicorn` starts, so the schema is created automatically on first deploy — no manual migration step. If your Postgres plan/tier doesn't support the `vector` extension, that one migration fails gracefully and everything else still applies (see DATABASE.md's pgvector note); semantic memory retrieval degrades gracefully in that case, it doesn't crash the app.
5. Once deployed, note the API's public URL (`https://lingoadapt-api-XXXX.onrender.com`) — you'll need it for the frontend.
6. **Add a Celery Beat service** if you want the four background jobs (recommendation refresh, due-review reminders, memory summarization, stale-session cleanup — `app/tasks/jobs.py`) to run on their own schedule rather than only when manually triggered. `render.yaml` doesn't include one yet: add a second `worker`-type service with `startCommand: celery -A app.tasks.celery_app beat --loglevel=info`, sharing the same env vars as `lingoadapt-worker`.

### 2. Frontend — Vercel

1. In the Vercel dashboard: **Add New → Project**, import the same GitHub repo.
2. **Root Directory**: set to `apps/web` (this is a monorepo — Vercel needs to know where the Next.js app actually lives; this is a one-time project setting, not something expressible in a committed config file for a subdirectory app).
3. Vercel auto-detects Next.js; no build command changes needed.
4. Environment variable: `NEXT_PUBLIC_API_URL` = the Render API URL from step 1.6 above.
5. Deploy. Note the resulting Vercel domain (`https://your-project.vercel.app`, or a custom domain if configured).

### 3. Close the loop: CORS

The backend's `CORS_ORIGINS` was set to a placeholder during Render setup. Go back to `lingoadapt-api`'s environment variables on Render and set:
```
CORS_ORIGINS=["https://your-project.vercel.app"]
```
(JSON array syntax, real frontend origin only — see SECURITY.md). Save; Render redeploys automatically. Without this step, the frontend can reach the API directly via server-side calls but browser-side requests will be blocked by CORS.

### 4. Verify

- `GET https://<render-api-url>/health` → `{"status": "ok", ...}`
- `GET https://<render-api-url>/health/ready` → checks DB + Redis, `503` if either is down
- Visit the Vercel URL, register an account, complete onboarding, send a tutor message.

## Docker Compose (local dev / self-hosting)

```bash
cp apps/api/.env.example apps/api/.env   # edit JWT_SECRET at minimum
docker compose up --build
```

Services: `postgres` (pgvector-enabled image), `redis`, `api` (its `command:` override runs `alembic upgrade head` then `uvicorn` — the committed Dockerfile's own `CMD` is bare `uvicorn`, so if you're building the image for a platform other than Docker Compose, replicate that migration step yourself, e.g. via a `startCommand` override as `render.yaml` does), `worker` (Celery), `web` (Next.js production build). `pgadmin` is available under the `tools` profile: `docker compose --profile tools up`.

**Background jobs**: the `worker` service runs Celery workers but not the periodic scheduler — add a `beat` service (`command: celery -A app.tasks.celery_app beat --loglevel=info`) or run the worker with `-B` for a combined single-instance dev/demo setup, or the four real jobs will only ever run when triggered manually.

## Production checklist

- [x] `JWT_SECRET` — `render.yaml` uses `generateValue: true`, a strong random secret with no manual step. If deploying elsewhere, set one explicitly (never the dev default).
- [x] `ENV=production`, `DEBUG=false` — set in `render.yaml` (also enables the `Strict-Transport-Security` header — see SECURITY.md).
- [x] `DATABASE_URL` / `REDIS_URL` point at managed instances via `render.yaml`'s `fromDatabase`/`fromService` — the Postgres instance **must** support the `vector` extension for semantic memory (Render's managed Postgres does; see DATABASE.md).
- [ ] Set `LLM_PROVIDER` to `anthropic` or `openai` with a real key — the mock provider is fine for a demo/portfolio deploy but never for one you expect real learners to use.
- [ ] Set `CORS_ORIGINS` to the real frontend origin (step 3 above) — this can't be automated since the Vercel domain isn't known until after that deploy.
- [x] Rate limiting is already wired up (`app/core/rate_limit.py`, Redis-backed, fails open) on auth/chat/practice/voice endpoints — tune the per-endpoint limits in each router if your traffic profile differs from the defaults.
- [ ] Configure `SENTRY_DSN` for error tracking if desired.
- [ ] Add a Celery Beat service (step 1.6 above) if you want background jobs to run automatically rather than only on manual/API trigger.
- [x] Render's health check is pointed at `GET /health` (liveness, no dependency checks). Point any load balancer/orchestrator readiness probe at `GET /health/ready` (checks DB + Redis) if you add one.
- [x] `render.yaml`'s `startCommand` runs `alembic upgrade head` as part of the release process.

## Scaling notes (section 107 — designed for, not implemented)

- `User.organization_id` / `User.teacher_id` are present but nullable — the schema doesn't need a migration to support future org/teacher features, just new endpoints.
- `Subscription.ai_tokens_used_month` / `voice_minutes_used_month` are present for future usage-limit enforcement; nothing currently increments them.
- The agent graph is stateless per-request (a fresh graph is compiled and bound to that request's DB session), so horizontal scaling of the API process is straightforward — there's no in-process session affinity requirement.

## CI

`.github/workflows/ci.yml` runs on every push/PR to `main`: backend lint (ruff, including security rules) + `pip-audit` + migrations against a real Postgres service container + pytest with coverage; frontend typecheck + lint + `npm audit` + vitest + production build; then Docker image builds for all three services (api, worker, web). No deploy step is included — Render redeploys automatically on push to `main` once the Blueprint is connected; Vercel does the same for the frontend.
