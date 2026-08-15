# Security

## Auth

- Passwords hashed with `bcrypt` directly (`app/core/security.py`) — not `passlib`, whose bcrypt backend detection is broken against `bcrypt>=4.1` (a real upstream incompatibility hit during development; see git history / ARCHITECTURE decisions).
- JWT (`python-jose`, HS256), 7-day default expiry, `sub` claim is the user UUID.
- `core/deps.get_current_user` validates the token and loads the user on every authenticated request; `get_current_admin` additionally checks `is_admin`.

## Tenant isolation (section 36, the most important invariant in this codebase)

`core/deps.get_learner_profile` resolves the caller's *own* `LearnerProfile` from their authenticated user — **no endpoint anywhere accepts a client-supplied `learner_profile_id`**. Every learner-data route (`chat`, `practice`, `vocabulary`, `progress`, `mistakes`, `recommendations`, `voice`) depends on this. Ownership is additionally checked explicitly where a resource is looked up by its own id (e.g. `practice.py::submit` checks `question.for_learner_profile_id == learner_profile.id`).

## Prompt injection (section 43, section 90)

`app/ai/prompts/base.py`:
- `SAFETY_PREAMBLE` tells the model that text inside `<learner_message>` tags is untrusted content to analyze, never instructions — even if it claims to be a system message or asks the model to reveal its instructions.
- `wrap_learner_message()` strips any `</learner_message>` sequence from the input before wrapping it, so injected text can't forge a tag boundary and escape the wrapper.
- Server-computed metrics (adaptation/teaching-strategy prompts) are never wrapped this way because they're trusted, not learner-authored.

## Input validation

All request/response shapes are Pydantic models (`app/schemas/`) — FastAPI rejects malformed input before it reaches business logic. `RegisterRequest.password` has a `min_length=8`. Audio uploads are capped at 15MB.

## Error handling (section 58)

`app/core/errors.py` registers handlers for `HTTPException`, `RequestValidationError`, and a catch-all `Exception` handler — every error response has the shape `{"success": false, "error": {"code", "message"}, "request_id"}`. Unhandled exceptions are logged with full detail server-side (structlog, JSON) but never leak a stack trace to the client. Every request gets an `x-request-id` (set by middleware in `main.py`), echoed in both the response header and any error body, for support/debugging traceability.

## Audit logging

`AuditLog` rows are written on register, login, data export, and account deactivation (`app/services/auth_service.py`, `app/api/v1/settings.py`).

## Rate limiting (section 43, 71)

`app/core/rate_limit.py::RateLimit` — a Redis-backed fixed-window counter (`INCR` + `EXPIRE`), applied as a FastAPI dependency to the endpoints that matter most: `auth/register` (5/hour/IP), `auth/login` (10/5min/IP — brute-force protection), `chat/message` (30/min/user), `voice/transcribe` (20/min/user), `voice/synthesize` (40/min/user), `practice/next` (20/min/user — these three guard against runaway LLM-call cost, not just abuse). Keys by authenticated user id when available (set on `request.state` by `get_current_user`), else client IP. **Fails open**: if Redis is unreachable, requests are allowed through with a warning logged rather than taking the API down — verified locally by hammering `/auth/login` past its limit and confirming `429 Too Many Requests` at request 11 of a 10/5min limit.

## Security headers

`app/main.py::security_headers_middleware` sets `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin` on every response, plus `Strict-Transport-Security` when `ENV=production`.

## Health checks

`GET /health` (liveness — no dependency checks, always fast) and `GET /health/ready` (readiness — actually pings Postgres and Redis, returns `503` if either is down) are separate on purpose, matching the standard k8s liveness/readiness probe split.

## Dependency vulnerability scanning (section 70)

CI runs `pip-audit` (backend) and `npm audit` (frontend) on every push — see `.github/workflows/ci.yml`. Findings as of this build:

- **Backend**: `ecdsa` (a transitive dependency of `python-jose`) has an open CVE (PYSEC-2026-1325) with no fixed version yet. **Accepted, low risk**: this application exclusively uses `JWT_ALGORITHM=HS256` (HMAC), never an ECDSA-based algorithm (ES256/etc.), so the vulnerable signing/verification code path in `ecdsa` is never invoked by any code in this repo.
- **Frontend**: upgraded `next` 15.1.4 → 15.5.23 during this build specifically to close a long list of real CVEs (RCE in the React Flight protocol, SSRF via Server Actions/Middleware, cache poisoning, auth bypass in Middleware, multiple DoS vectors — see the advisory list in git history / PR description). Remaining `npm audit` findings after that upgrade all require a **major** Next.js 16 upgrade (breaking changes, out of scope for this pass) and are **accepted as low risk** given this app's actual usage: the `sharp`/`postcss` findings live inside `next`'s own bundled `next/image` optimizer, which this codebase never imports (verified: no `next/image` usage anywhere in `src/`); the `esbuild`/`vite`/`vitest` finding is in a dev-only test-runner dependency never shipped in the production build.

## What's not implemented (be honest about the gaps)

- **CSRF**: not applicable as built — the API is a pure JSON Bearer-token API with no cookie-based session, so CSRF (which targets cookie auth) isn't a relevant threat model here. If cookie-based auth is added later, CSRF protection must be added with it.
- **Secrets management**: `.env` files for local dev; no Vault/Secrets Manager integration. Never commit a real `.env`.
- **Admin data exposure**: `app/services/admin_service.py` intentionally returns aggregate counts only — no individual conversation content is queryable through any admin endpoint in this build (section 56).
- **Content Security Policy**: not set — this is a pure JSON API (the frontend is a separate Next.js app with its own CSP considerations, not covered here).
