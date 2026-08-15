"""Aggregation queries backing the Progress and Dashboard pages (sections 24, 28).
Nothing here is fabricated — every number is derived from real rows."""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import AnalyticsEvent
from app.models.errors import LearnerError
from app.models.language import Skill
from app.models.learner import LearnerProfile
from app.models.mastery import SkillMastery
from app.models.practice import PracticeAttempt
from app.models.session import LearningSession
from app.models.vocabulary import VocabularyItem


async def get_dashboard_summary(db: AsyncSession, *, learner_profile: LearnerProfile, user_id: UUID) -> dict:
    mastery_rows = (await db.execute(
        select(SkillMastery, Skill).join(Skill, Skill.id == SkillMastery.skill_id)
        .where(SkillMastery.learner_profile_id == learner_profile.id)
    )).all()

    weak_areas = sorted(
        [{"skill_code": s.code, "skill_name": s.name, "mastery": m.mastery} for m, s in mastery_rows],
        key=lambda x: x["mastery"],
    )[:5]

    vocab_counts = (await db.execute(
        select(VocabularyItem.status, func.count()).where(VocabularyItem.learner_profile_id == learner_profile.id).group_by(VocabularyItem.status)
    )).all()

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    weekly_minutes = (await db.execute(
        select(func.coalesce(func.sum(LearningSession.duration_seconds), 0))
        .where(LearningSession.user_id == user_id, LearningSession.started_at >= week_ago)
    )).scalar_one() / 60

    recent_errors = (await db.execute(
        select(LearnerError).where(LearnerError.learner_profile_id == learner_profile.id)
        .order_by(LearnerError.last_seen_at.desc()).limit(5)
    )).scalars().all()

    return {
        "cefr_level": learner_profile.cefr_level,
        "streak_days": learner_profile.streak_days,
        "total_study_minutes": learner_profile.total_study_minutes,
        "weekly_study_minutes": round(weekly_minutes, 1),
        "abilities": {
            "grammar": learner_profile.grammar_ability, "vocabulary": learner_profile.vocabulary_ability,
            "speaking": learner_profile.speaking_ability, "listening": learner_profile.listening_ability,
            "reading": learner_profile.reading_ability, "writing": learner_profile.writing_ability,
            "pronunciation": learner_profile.pronunciation_ability, "fluency": learner_profile.fluency_ability,
        },
        "weak_areas": weak_areas,
        "vocabulary_counts": {status: count for status, count in vocab_counts},
        "recent_mistakes": [
            {"category": e.category, "occurrence_count": e.occurrence_count, "last_seen_at": e.last_seen_at.isoformat(), "trend": e.trend}
            for e in recent_errors
        ],
    }


async def get_mastery_history(db: AsyncSession, *, learner_profile_id: UUID) -> list[dict]:
    rows = (await db.execute(
        select(SkillMastery, Skill).join(Skill, Skill.id == SkillMastery.skill_id)
        .where(SkillMastery.learner_profile_id == learner_profile_id).order_by(Skill.category, Skill.name)
    )).all()
    return [{"skill_code": s.code, "skill_name": s.name, "category": s.category, "mastery": m.mastery,
             "attempts": m.attempts, "next_review_at": m.next_review_at.isoformat() if m.next_review_at else None}
            for m, s in rows]


async def get_practice_accuracy_trend(db: AsyncSession, *, user_id: UUID, days: int = 14) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (await db.execute(
        select(func.date(PracticeAttempt.attempted_at), func.avg(func.cast(PracticeAttempt.is_correct, Integer)))
        .where(PracticeAttempt.user_id == user_id, PracticeAttempt.attempted_at >= since)
        .group_by(func.date(PracticeAttempt.attempted_at)).order_by(func.date(PracticeAttempt.attempted_at))
    )).all()
    return [{"date": str(d), "accuracy": round(float(a), 2)} for d, a in rows]


async def get_activity_summary(db: AsyncSession, *, user_id: UUID, days: int = 30) -> dict:
    """Daily event counts (for a streak/activity calendar) + a breakdown by
    event type — both derived from real AnalyticsEvent rows (section 85-86),
    not inferred after the fact."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    daily_rows = (await db.execute(
        select(func.date(AnalyticsEvent.created_at), func.count())
        .where(AnalyticsEvent.user_id == user_id, AnalyticsEvent.created_at >= since)
        .group_by(func.date(AnalyticsEvent.created_at)).order_by(func.date(AnalyticsEvent.created_at))
    )).all()

    type_rows = (await db.execute(
        select(AnalyticsEvent.event_type, func.count())
        .where(AnalyticsEvent.user_id == user_id, AnalyticsEvent.created_at >= since)
        .group_by(AnalyticsEvent.event_type).order_by(func.count().desc())
    )).all()

    return {
        "daily_counts": [{"date": str(d), "count": c} for d, c in daily_rows],
        "event_breakdown": [{"event_type": t, "count": c} for t, c in type_rows],
    }
