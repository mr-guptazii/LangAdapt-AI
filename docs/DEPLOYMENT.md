# Deployment

Three paths are documented, in the order most people reading this actually
want them: free self-hosted VM, then the paid managed-platform split, then
plain local Docker Compose for development.

## Self-hosted VM (genuinely free — Oracle Cloud "Always Free")

Everything (API, worker, Celery beat, Postgres+pgvector, Redis, frontend, TLS)
on one VM you control, via `infrastructure/vm/docker-compose.prod.yml`. No
platform fees; you're trading that for doing your own ops (updates, restarts,
backups). This is genuinely $0/month forever on Oracle's Always Free tier —
not a time-limited trial.

### 1. Provision the VM (you do this — no credentials for OCI exist in this environment)

1. Create an Oracle Cloud account at [cloud.oracle.com](https://cloud.oracle.com) (a card is required for identity verification; Always Free resources are never billed).
2. **Create → Compute → Instance**. Shape: **VM.Standard.A1.Flex** (Ampere ARM), sized at **2 OCPU / 12GB RAM** — as of mid-2026 that's the full Always Free Ampere allowance (Oracle halved it from 4 OCPU/24GB in June 2026 with no announcement, so don't trust older tutorials claiming 4/24). Image: **Ubuntu 22.04 or 24.04 (minimal)** — simpler firewall defaults than Oracle Linux's image, which ships `firewalld` active.
3. Note the VM's **public IP**. Add your SSH key during creation (or use the OCI-generated one).
4. **Open ports in the OCI Console** (separate from anything on the VM itself): the instance's subnet **Security List** (or a Network Security Group) needs ingress rules for TCP 22 (SSH, usually pre-opened), 80, and 443 from `0.0.0.0/0`. This is the single most common thing people miss on a first OCI deploy — the VM's own firewall can be wide open and the app will still be unreachable if this cloud-level rule isn't set.
5. Optional but recommended: point a domain's DNS `A` record at the VM's public IP, for automatic HTTPS (see below). A bare IP works too, over plain HTTP only.

### 2. Bootstrap the VM

SSH in, then either run `infrastructure/vm/setup.sh` directly from a fresh clone, or pipe it:
```bash
ssh ubuntu@<vm-public-ip>
curl -fsSL https://raw.githubusercontent.com/mr-guptazii/LangAdapt-AI/main/infrastructure/vm/setup.sh | bash
```
First run installs Docker, opens the VM's own `ufw` firewall (22/80/443), clones the repo, and creates `apps/api/.env` from the template — then stops and tells you to edit it. Fill in at minimum:
- `JWT_SECRET` — `openssl rand -hex 32`
- `POSTGRES_PASSWORD`, `REDIS_PASSWORD` — real random values (these two are only read by `docker-compose.prod.yml`, not local dev)
- `DOMAIN` — your real domain for automatic Let's Encrypt HTTPS via Caddy, or leave blank to serve plain HTTP on the bare IP
- `LLM_PROVIDER` (+ keys) — `mock` works with zero setup; see `.env.example` for real-provider values

Re-run the script (or run its last command yourself):
```bash
cd ~/lingoadapt
docker compose -f infrastructure/vm/docker-compose.prod.yml --env-file apps/api/.env up -d --build
```

### 3. What's different from local Docker Compose

- **Single domain, no CORS to configure.** `docker-compose.prod.yml` sets the frontend's `NEXT_PUBLIC_API_URL` to an *empty string*, which makes every API call same-origin (`fetch("/api/v1/...")` resolves against whatever domain you're on). Caddy (`infrastructure/vm/Caddyfile`) path-routes `/api/*` and `/health*` to the backend and everything else to the frontend, all under one origin — there's no second origin for CORS_ORIGINS to need to list.
- **Postgres and Redis are never exposed to the host's public interface** — no `ports:` mapping for either, unlike the local dev `docker-compose.yml` (which does expose them, deliberately, for local GUI-client convenience). Only Caddy publishes 80/443.
- **Celery Beat is included as its own service** (`beat`), unlike `render.yaml` or local Compose — so the four background jobs (recommendation refresh, due-review reminders, memory summarization, stale-session cleanup — `app/tasks/jobs.py`) actually run on their schedule, not just on manual trigger.
- Migrations run automatically via the `api` service's `command:` override (same pattern as local Compose).

### 4. Verify

```bash
curl http://<vm-ip-or-domain>/health
curl http://<vm-ip-or-domain>/health/ready   # checks DB + Redis
```
Then visit the domain/IP in a browser, register, complete onboarding, send a tutor message.

### 5. Keeping it running

`restart: unless-stopped` is set on every service, so the stack survives a VM reboot once Docker's own systemd service is enabled (the `get.docker.com` install script does this automatically). To deploy an update: `git pull && docker compose -f infrastructure/vm/docker-compose.prod.yml --env-file apps/api/.env up -d --build`.

---

## Vercel (frontend) + Render (backend) — paid managed-platform alternative

Same architecture, hosted instead of self-managed: Vercel for the Next.js
frontend, Render for API + worker + Postgres + Redis via `render.yaml`. No
server to maintain, but **not free** — background workers and Redis have no
free tier on Render (roughly $30/mo minimum for this app's shape as of this
writing; the VM path above is the $0 alternative). Both platforms require
your own login — an agent can prepare the code and configs but can't
complete an OAuth flow on your behalf.

### 1. Backend — Render

1. Push this repo to GitHub (already done if you're reading this from the deployed repo).
2. In the Render dashboard: **New → Blueprint**, select this repo. Render reads `render.yaml` at the repo root and provisions four resources: `lingoadapt-db` (Postgres, pgvector-enabled), `lingoadapt-redis` (Key Value), `lingoadapt-api` (web service), `lingoadapt-worker` (Celery worker).
3. You'll be prompted for the `sync: false` env vars during creation, with no defaults (Render disallows combining a default `value` with `sync: false`) — at minimum decide `LLM_PROVIDER`:
   - `mock` — boots immediately, zero cost, zero setup (see AI_SYSTEM.md for what this means in practice).
   - `anthropic` + `ANTHROPIC_API_KEY` — real Claude.
   - `openai` + `OPENAI_API_KEY` (+ `OPENAI_BASE_URL`, `OPENAI_MODEL_FAST`, `OPENAI_MODEL_STRONG`) — real OpenAI, or any OpenAI-compatible backend (NVIDIA NIM, Gemini's compat endpoint, Groq, etc.) — see `.env.example` for exact per-backend values, and AI_SYSTEM.md for two real gotchas hit getting Gemini working (a token-budget floor for reasoning models, and a fallback for backends that don't reliably honor forced tool-calling).
   - Enter `["http://localhost:3000"]` as a placeholder for `CORS_ORIGINS` — you'll fix this in step 3.
4. `lingoadapt-api`'s `dockerCommand` runs `alembic upgrade head` before `uvicorn` starts (note: `dockerCommand`, not `startCommand` — Render reserves the latter for native/buildpack runtimes; a docker-runtime service that sets `startCommand` fails Blueprint validation), so the schema is created automatically on first deploy. If your Postgres plan/tier doesn't support the `vector` extension, that one migration fails gracefully and everything else still applies (see DATABASE.md's pgvector note); semantic memory retrieval degrades gracefully in that case, it doesn't crash the app.
5. Once deployed, note the API's public URL (`https://lingoadapt-api-XXXX.onrender.com`) — you'll need it for the frontend.
6. **Add a Celery Beat service** if you want the four background jobs to run on their own schedule rather than only when manually triggered. `render.yaml` doesn't include one yet: add a second `worker`-type service with `dockerCommand: celery -A app.tasks.celery_app beat --loglevel=info`, sharing the same env vars as `lingoadapt-worker`.

### 2. Frontend — Vercel

1. In the Vercel dashboard: **Add New → Project**, import the same GitHub repo.
2. **Root Directory**: set to `apps/web` (this is a monorepo — Vercel needs to know where the Next.js app actually lives; this is a one-time project setting, not something expressible in a committed config file for a subdirectory app).
3. Vercel auto-detects Next.js; no build command changes needed.
4. Environment variable: `NEXT_PUBLIC_API_URL` = the Render API URL from step 1.5 above.
5. Deploy. Note the resulting Vercel domain (`https://your-project.vercel.app`, or a custom domain if configured).

### 3. Close the loop: CORS

Go back to `lingoadapt-api`'s environment variables on Render and set:
```
CORS_ORIGINS=["https://your-project.vercel.app"]
```
(JSON array syntax, real frontend origin only — see SECURITY.md). Save; Render redeploys automatically. Without this step, browser-side requests from the Vercel frontend are blocked by CORS. (This CORS step doesn't exist on the self-hosted VM path above — see its "single domain, no CORS" note.)

### 4. Verify

- `GET https://<render-api-url>/health` → `{"status": "ok", ...}`
- `GET https://<render-api-url>/health/ready` → checks DB + Redis, `503` if either is down
- Visit the Vercel URL, register an account, complete onboarding, send a tutor message.

---

## Docker Compose (local development only)

```bash
cp apps/api/.env.example apps/api/.env   # edit JWT_SECRET at minimum
docker compose up --build
```

Services: `postgres` (pgvector-enabled image), `redis`, `api` (its `command:` override runs `alembic upgrade head` then `uvicorn` — the committed Dockerfile's own `CMD` is bare `uvicorn`), `worker` (Celery), `web` (Next.js production build). `pgadmin` is available under the `tools` profile: `docker compose --profile tools up`. Postgres/Redis ports are deliberately exposed to the host here (`5432`/`6379`) for local GUI-client convenience — this is a dev-only setup, not the pattern the self-hosted VM path uses.

**Background jobs**: the `worker` service runs Celery workers but not the periodic scheduler — add a `beat` service (`command: celery -A app.tasks.celery_app beat --loglevel=info`) or run the worker with `-B` for a combined single-instance dev/demo setup, or the four real jobs will only ever run when triggered manually.

## Production checklist

- [x] `JWT_SECRET` — random on both paths (`openssl rand -hex 32` on the VM path, `generateValue: true` on Render). Never the dev default.
- [x] `ENV=production`, `DEBUG=false` — set on both paths (also enables the `Strict-Transport-Security` header — see SECURITY.md).
- [x] `DATABASE_URL` / `REDIS_URL` point at real instances on both paths; Postgres **must** support the `vector` extension for semantic memory (see DATABASE.md).
- [ ] Set `LLM_PROVIDER` to `anthropic` or `openai` with a real key — the mock provider is fine for a demo/portfolio deploy but never for one you expect real learners to use.
- [ ] CORS: only relevant on the Vercel+Render path (step 3 there) — the VM path has no second origin to configure.
- [x] Rate limiting is already wired up (`app/core/rate_limit.py`, Redis-backed, fails open) on auth/chat/practice/voice endpoints — tune the per-endpoint limits in each router if your traffic profile differs from the defaults.
- [ ] Configure `SENTRY_DSN` for error tracking if desired.
- [x] Celery Beat: included by default on the VM path (`beat` service); an extra manual step on Render (step 1.6 above).
- [x] Health checks: `GET /health` (liveness) and `GET /health/ready` (readiness — DB + Redis).
- [x] Migrations run automatically as part of the release/start command on every path documented here.

## Scaling notes (section 107 — designed for, not implemented)

- `User.organization_id` / `User.teacher_id` are present but nullable — the schema doesn't need a migration to support future org/teacher features, just new endpoints.
- `Subscription.ai_tokens_used_month` / `voice_minutes_used_month` are present for future usage-limit enforcement; nothing currently increments them.
- The agent graph is stateless per-request (a fresh graph is compiled and bound to that request's DB session), so horizontal scaling of the API process is straightforward — there's no in-process session affinity requirement.

## CI

`.github/workflows/ci.yml` runs on every push/PR to `main`: backend lint (ruff, including security rules) + `pip-audit` + migrations against a real Postgres service container + pytest with coverage; frontend typecheck + lint + `npm audit` + vitest + production build; then Docker image builds for all three services (api, worker, web). No deploy step is included — Render/Vercel redeploy automatically on push to `main` once connected; the self-hosted VM needs a manual `git pull && docker compose up -d --build` (or wire up a `git pull` cron/webhook yourself).
