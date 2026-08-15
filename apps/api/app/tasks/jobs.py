"""Real background job implementations (section 38). Each Celery task is a
thin sync wrapper (`asyncio.run`) around an async implementation that uses the
same services/models the API does — no separate "batch" logic that could
drift from the request-time behavior.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.ai.prompts.assessment import build_learner_model_summary_prompt
from app.ai.providers.base import LLMMessage, ModelTier
from app.ai.providers.factory import get_llm_provider
from app.core.logging import get_logger
from app.database.session import AsyncSessionLocal
from app.memory.service import store_memory
from app.models.errors import LearnerError
from app.models.learner import LearnerProfile
from app.models.mastery import SkillMastery
from app.models.session import LearningSession
from app.models.system import Notification
from app.models.user import User
from app.schemas.agent_io import LearnerMemoryBatch
from app.services import ai_usage_service, recommendation_service
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="app.tasks.jobs.generate_recommendations_for_active_users")
def generate_recommendations_for_active_users() -> int:
    return asyncio.run(_generate_recommendations_for_active_users())


async def _generate_recommendations_for_active_users() -> int:
    async with AsyncSessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        profiles = (await db.execute(
            select(LearnerProfile)
            .join(User, User.id == LearnerProfile.user_id)
            .where(User.is_active.is_(True), LearnerProfile.updated_at >= cutoff)
        )).scalars().all()

        processed = 0
        for profile in profiles:
            try:
                await recommendation_service.generate_recommendations(db, learner_profile=profile)
                processed += 1
            except Exception:
                logger.warning("recommendation_job_failed_for_profile", learner_profile_id=str(profile.id))
        logger.info("recommendation_job_complete", profiles_processed=processed)
        return processed


@celery_app.task(name="app.tasks.jobs.send_due_review_reminders")
def send_due_review_reminders() -> int:
    return asyncio.run(_send_due_review_reminders())


async def _send_due_review_reminders() -> int:
    """Real query for real due reviews (section 55/17) — one Notification row
    per learner who actually has something due, not a blanket broadcast."""
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        due_counts = (await db.execute(
            select(SkillMastery.learner_profile_id, LearnerProfile.user_id)
            .join(LearnerProfile, LearnerProfile.id == SkillMastery.learner_profile_id)
            .where(SkillMastery.next_review_at.is_not(None), SkillMastery.next_review_at <= now)
        )).all()

        by_user: dict = {}
        for _profile_id, user_id in due_counts:
            by_user[user_id] = by_user.get(user_id, 0) + 1

        for user_id, count in by_user.items():
            db.add(Notification(
                user_id=user_id, type="review_due", title=f"{count} review{'s' if count != 1 else ''} due today",
                body=f"You have {count} skill{'s' if count != 1 else ''} due for spaced-repetition review.",
                sent_at=now,
            ))
        await db.commit()
        logger.info("review_reminder_job_complete", notifications_sent=len(by_user))
        return len(by_user)


@celery_app.task(name="app.tasks.jobs.summarize_recent_learner_activity")
def summarize_recent_learner_activity() -> int:
    return asyncio.run(_summarize_recent_learner_activity())


async def _summarize_recent_learner_activity() -> int:
    """The background, strong-model learner-model summarization pass
    (section 8/120): turns a batch of raw errors into structured, reusable
    LearnerMemory statements — synthesis, not a restatement of raw events."""
    async with AsyncSessionLocal() as db:
        since = datetime.now(timezone.utc) - timedelta(days=1)
        recent_errors = (await db.execute(
            select(LearnerError).where(LearnerError.last_seen_at >= since)
        )).scalars().all()

        by_profile: dict = {}
        for err in recent_errors:
            by_profile.setdefault(err.learner_profile_id, []).append(err)

        provider = get_llm_provider()
        summarized = 0
        for profile_id, errors in by_profile.items():
            events = [{"category": e.category, "occurrence_count": e.occurrence_count, "trend": e.trend, "severity": e.severity} for e in errors]
            messages = build_learner_model_summary_prompt(events=events)
            llm_messages = [LLMMessage(role=m["role"], content=m["content"]) for m in messages]
            try:
                result, usage = await provider.structured(llm_messages, LearnerMemoryBatch, tier=ModelTier.STRONG, max_tokens=500)
            except Exception:
                logger.warning("memory_summarization_failed", learner_profile_id=str(profile_id))
                continue
            ai_usage_service.log(db, user_id=None, session_id=None, node="memory_summarizer", usage=usage, tier=ModelTier.STRONG)
            for statement in result.statements:
                await store_memory(
                    db, learner_profile_id=profile_id, memory_type=statement.memory_type,
                    content=statement.content, importance=statement.importance,
                )
            summarized += 1
        await db.commit()
        logger.info("memory_summarization_job_complete", profiles_summarized=summarized)
        return summarized


@celery_app.task(name="app.tasks.jobs.cleanup_stale_sessions")
def cleanup_stale_sessions() -> int:
    return asyncio.run(_cleanup_stale_sessions())


async def _cleanup_stale_sessions() -> int:
    """Auto-closes sessions a client never explicitly ended (dropped
    connection, closed tab) so is_active/duration stay accurate for
    analytics rather than leaking 'active forever' sessions."""
    async with AsyncSessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        stale = (await db.execute(
            select(LearningSession).where(LearningSession.is_active.is_(True), LearningSession.started_at < cutoff)
        )).scalars().all()

        for session in stale:
            session.is_active = False
            session.ended_at = session.started_at + timedelta(minutes=15)  # conservative estimate, not left null
            session.duration_seconds = 15 * 60

        await db.commit()
        logger.info("cleanup_job_complete", sessions_closed=len(stale))
        return len(stale)
