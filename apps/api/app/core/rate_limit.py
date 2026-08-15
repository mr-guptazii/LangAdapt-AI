"""Redis-backed rate limiting (section 43, 71). A simple fixed-window counter
(INCR + EXPIRE) — not a sliding-window/token-bucket algorithm, which is a
deliberate simplification: fixed-window is what a single INCR/EXPIRE pair can
implement without Lua scripting, and is precise enough for abuse prevention on
auth and AI-calling endpoints (its only real weakness — allowing up to 2x the
limit right at a window boundary — doesn't matter for this use case).

Fails OPEN, not closed: if Redis is unreachable, requests are allowed through
with a warning logged, rather than taking the whole API down because the rate
limiter's own dependency is unavailable. This mirrors the graceful-degradation
pattern used elsewhere (mock providers, pgvector fallback in memory/service.py).
"""
from functools import lru_cache

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache
def get_redis_client() -> aioredis.Redis:
    # protocol=2: see admin_service.py's note — some Redis deployments don't
    # support the RESP3 HELLO handshake redis-py attempts by default.
    return aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2, protocol=2)


def _client_key(request: Request, user_id: str | None) -> str:
    if user_id:
        return f"user:{user_id}"
    # X-Forwarded-For is only trusted because this app is expected to sit
    # behind a reverse proxy in production that sets it; request.client.host
    # is the fallback for direct/local access.
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    return f"ip:{ip}"


class RateLimit:
    """Dependency factory: RateLimit(times=5, seconds=60) limits a route to 5
    calls per 60s per caller (authenticated user if available, else client IP)."""

    def __init__(self, times: int, seconds: int, scope: str):
        self.times = times
        self.seconds = seconds
        self.scope = scope  # distinguishes routes sharing a caller key, e.g. "login" vs "chat"

    async def __call__(self, request: Request) -> None:
        # Authenticated routes attach the user during their own get_current_user
        # dependency; we read it back off request.state if that ran first, and
        # fall back to IP otherwise (e.g. login/register, which are unauthenticated).
        user_id = getattr(request.state, "user_id", None)
        key = f"ratelimit:{self.scope}:{_client_key(request, user_id)}"

        try:
            client = get_redis_client()
            count = await client.incr(key)
            if count == 1:
                await client.expire(key, self.seconds)
        except Exception:
            logger.warning("rate_limit_check_failed_open", scope=self.scope)
            return

        if count > self.times:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Limit is {self.times} per {self.seconds}s for this action.",
            )
