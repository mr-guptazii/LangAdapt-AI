"""Admin dashboard aggregate queries (section 56-57). Every number here is a
real query result — no synthetic placeholders. Individual conversation content
is never exposed through any function in this module (section 56)."""
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.analytics import AIUsageLog, AnalyticsEvent
from app.models.errors import LearnerError
from app.models.learner import LearnerProfile
from app.models.session import LearningSession
from app.models.user import User


async def get_overview(db: AsyncSession) -> dict:
    now = timezone_now()
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    active_sessions = (await db.execute(select(func.count()).select_from(LearningSession).where(LearningSession.is_active))).scalar_one()

    week_ago = now - timedelta(days=7)
    active_users_7d = (await db.execute(
        select(func.count(func.distinct(AnalyticsEvent.user_id))).where(AnalyticsEvent.created_at >= week_ago)
    )).scalar_one()

    cefr_rows = (await db.execute(select(LearnerProfile.cefr_level, func.count()).group_by(LearnerProfile.cefr_level))).all()
    lang_rows = (await db.execute(select(LearnerProfile.target_language_code, func.count()).group_by(LearnerProfile.target_language_code))).all()

    return {
        "total_users": total_users,
        "active_users_7d": active_users_7d,
        "active_sessions": active_sessions,
        "cefr_distribution": {level: count for level, count in cefr_rows},
        "language_distribution": {lang: count for lang, count in lang_rows},
        "note": "Aggregate metrics only — individual conversation content is never surfaced here.",
    }


async def get_ai_usage_summary(db: AsyncSession, *, days: int = 30) -> dict:
    since = timezone_now() - timedelta(days=days)

    totals = (await db.execute(
        select(func.count(), func.coalesce(func.sum(AIUsageLog.input_tokens), 0),
               func.coalesce(func.sum(AIUsageLog.output_tokens), 0), func.coalesce(func.sum(AIUsageLog.estimated_cost_usd), 0.0))
        .where(AIUsageLog.created_at >= since)
    )).one()
    call_count, input_tokens, output_tokens, cost = totals

    by_model = (await db.execute(
        select(AIUsageLog.model, AIUsageLog.provider, func.count(), func.coalesce(func.sum(AIUsageLog.estimated_cost_usd), 0.0))
        .where(AIUsageLog.created_at >= since).group_by(AIUsageLog.model, AIUsageLog.provider).order_by(func.count().desc())
    )).all()

    by_node = (await db.execute(
        select(AIUsageLog.node, func.count()).where(AIUsageLog.created_at >= since).group_by(AIUsageLog.node).order_by(func.count().desc())
    )).all()

    daily_cost = (await db.execute(
        select(func.date(AIUsageLog.created_at), func.coalesce(func.sum(AIUsageLog.estimated_cost_usd), 0.0))
        .where(AIUsageLog.created_at >= since).group_by(func.date(AIUsageLog.created_at)).order_by(func.date(AIUsageLog.created_at))
    )).all()

    return {
        "period_days": days,
        "total_calls": call_count,
        "total_input_tokens": int(input_tokens),
        "total_output_tokens": int(output_tokens),
        "total_estimated_cost_usd": round(float(cost), 4),
        "by_model": [{"model": m, "provider": p, "calls": c, "estimated_cost_usd": round(float(cst), 4)} for m, p, c, cst in by_model],
        "by_node": [{"node": n, "calls": c} for n, c in by_node],
        "daily_cost_usd": [{"date": str(d), "cost": round(float(c), 4)} for d, c in daily_cost],
    }


async def get_common_errors(db: AsyncSession, *, limit: int = 10) -> list[dict]:
    rows = (await db.execute(
        select(LearnerError.category, func.count(func.distinct(LearnerError.learner_profile_id)), func.sum(LearnerError.occurrence_count))
        .group_by(LearnerError.category).order_by(func.sum(LearnerError.occurrence_count).desc()).limit(limit)
    )).all()
    return [{"category": category, "learners_affected": learners, "total_occurrences": int(total)} for category, learners, total in rows]


async def get_retention(db: AsyncSession) -> dict:
    now = timezone_now()
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    if total_users == 0:
        return {"dau": 0, "wau": 0, "mau": 0, "dau_mau_ratio": 0.0}

    async def _active_since(cutoff: datetime) -> int:
        return (await db.execute(
            select(func.count(func.distinct(AnalyticsEvent.user_id))).where(AnalyticsEvent.created_at >= cutoff)
        )).scalar_one()

    dau = await _active_since(now - timedelta(days=1))
    wau = await _active_since(now - timedelta(days=7))
    mau = await _active_since(now - timedelta(days=30))
    return {"dau": dau, "wau": wau, "mau": mau, "dau_mau_ratio": round(dau / mau, 2) if mau else 0.0}


async def get_system_health(db: AsyncSession) -> dict:
    db_healthy = True
    try:
        await db.execute(select(1))
    except Exception:
        db_healthy = False

    redis_healthy = True
    redis_latency_ms = None
    try:
        # protocol=2 (RESP2): forced explicitly because some Redis deployments
        # (older versions, some managed/proxy setups) don't support the RESP3
        # HELLO handshake redis-py attempts by default — RESP2 is universally
        # supported and all we need for a ping + the rate limiter's INCR/EXPIRE.
        client = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2, protocol=2)
        start = timezone_now()
        await client.ping()
        redis_latency_ms = int((timezone_now() - start).total_seconds() * 1000)
        await client.close()
    except Exception:
        redis_healthy = False

    row_counts = {}
    for label, model in [("users", User), ("sessions", LearningSession), ("ai_usage_logs", AIUsageLog), ("analytics_events", AnalyticsEvent)]:
        row_counts[label] = (await db.execute(select(func.count()).select_from(model))).scalar_one()

    return {
        "database": {"healthy": db_healthy},
        "redis": {"healthy": redis_healthy, "latency_ms": redis_latency_ms},
        "row_counts": row_counts,
        "note": "Job-failure tracking requires a Celery events consumer (e.g. Flower) and is not wired up in this build.",
    }


def timezone_now() -> datetime:
    return datetime.now(timezone.utc)
