"""Controlled tool layer (section 44). Every tool takes an explicit
learner_profile_id resolved server-side from the authenticated user — an agent
can never be handed a client-supplied id, which is what keeps cross-user data
access impossible even if a prompt injection tried to request it.
"""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.errors import LearnerError
from app.models.language import Skill
from app.models.learner import LearnerProfile, LearningPreference
from app.models.mastery import SkillMastery


async def get_learner_profile(db: AsyncSession, learner_profile_id: UUID) -> LearnerProfile | None:
    return await db.get(LearnerProfile, learner_profile_id)


async def get_learning_preferences(db: AsyncSession, learner_profile_id: UUID) -> LearningPreference | None:
    result = await db.execute(select(LearningPreference).where(LearningPreference.learner_profile_id == learner_profile_id))
    return result.scalar_one_or_none()


async def get_recent_errors(db: AsyncSession, learner_profile_id: UUID, limit: int = 5) -> list[LearnerError]:
    result = await db.execute(
        select(LearnerError)
        .where(LearnerError.learner_profile_id == learner_profile_id)
        .order_by(LearnerError.weakness_score.desc(), LearnerError.last_seen_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_skill_mastery(db: AsyncSession, learner_profile_id: UUID, skill_code: str) -> SkillMastery | None:
    result = await db.execute(
        select(SkillMastery)
        .join(Skill, Skill.id == SkillMastery.skill_id)
        .where(SkillMastery.learner_profile_id == learner_profile_id, Skill.code == skill_code)
    )
    return result.scalar_one_or_none()


async def get_or_create_skill_mastery(db: AsyncSession, learner_profile_id: UUID, skill_id: UUID) -> SkillMastery:
    result = await db.execute(
        select(SkillMastery).where(SkillMastery.learner_profile_id == learner_profile_id, SkillMastery.skill_id == skill_id)
    )
    mastery = result.scalar_one_or_none()
    if mastery is None:
        mastery = SkillMastery(learner_profile_id=learner_profile_id, skill_id=skill_id, mastery=0.0)
        db.add(mastery)
        await db.flush()
    return mastery


async def get_skill_by_code(db: AsyncSession, language_code: str, skill_code: str) -> Skill | None:
    result = await db.execute(select(Skill).where(Skill.language_code == language_code, Skill.code == skill_code))
    return result.scalar_one_or_none()


async def get_due_reviews(db: AsyncSession, learner_profile_id: UUID, limit: int = 10) -> list[SkillMastery]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(SkillMastery)
        .where(
            SkillMastery.learner_profile_id == learner_profile_id,
            SkillMastery.next_review_at.is_not(None),
            SkillMastery.next_review_at <= now,
        )
        .order_by(SkillMastery.next_review_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())
