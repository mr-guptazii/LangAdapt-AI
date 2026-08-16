"""Recommendation engine (section 45/87). Ranking is deterministic and
inspectable (never "just ask the LLM to pick"); the LLM's only job is to phrase
the already-ranked top candidates warmly (see build_recommendation_prompt).
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts.recommendation import build_recommendation_prompt
from app.ai.providers.base import LLMMessage, ModelTier
from app.ai.providers.factory import get_llm_provider
from app.models.language import Skill
from app.models.learner import LearnerProfile, LearningGoal
from app.models.recommendation import LearningRecommendation
from app.schemas.agent_io import RecommendationOutput
from app.services import ai_usage_service, event_service
from app.tools import learner_tools


async def _score_candidates(db: AsyncSession, learner_profile: LearnerProfile) -> list[dict]:
    candidates: list[dict] = []

    # 1. Weak/recurring errors (highest urgency signal).
    errors = await learner_tools.get_recent_errors(db, learner_profile.id, limit=5)
    for e in errors:
        candidates.append({
            "activity_type": "grammar", "title": f"Practice {e.category.replace('_', ' ')}",
            "reason_code": "recent_mistake", "target_skill_code": e.category,
            "priority_score": 0.5 + e.weakness_score * 0.4, "estimated_minutes": 8,
        })

    # 2. Due spaced-repetition reviews.
    due = await learner_tools.get_due_reviews(db, learner_profile.id, limit=5)
    for m in due:
        skill = await db.get(Skill, m.skill_id)
        if not skill:
            continue
        candidates.append({
            "activity_type": "vocabulary" if skill.category == "vocabulary" else "grammar",
            "title": f"Review {skill.name}", "reason_code": "due_review", "target_skill_code": skill.code,
            "priority_score": 0.55, "estimated_minutes": 5,
        })

    # 3. Goal-aligned conversation practice (variety signal — always include one).
    goals = (await db.execute(select(LearningGoal).where(LearningGoal.learner_profile_id == learner_profile.id))).scalars().all()
    goal_label = goals[0].goal_type.replace("_", " ") if goals else "everyday conversation"
    candidates.append({
        "activity_type": "conversation", "title": f"Have a conversation about {goal_label}",
        "reason_code": "goal_alignment", "target_skill_code": None, "priority_score": 0.45, "estimated_minutes": 7,
    })

    candidates.sort(key=lambda c: c["priority_score"], reverse=True)
    return candidates[:6]


async def generate_recommendations(db: AsyncSession, *, learner_profile: LearnerProfile, top_n: int = 3) -> list[LearningRecommendation]:
    candidates = await _score_candidates(db, learner_profile)
    if not candidates:
        return []

    provider = get_llm_provider()
    account = await learner_tools.get_profile_settings(db, learner_profile.user_id)
    interests = account.interests if (account and account.personalization_enabled) else []
    learner_summary = {
        "cefr_level": learner_profile.cefr_level, "grammar_ability": learner_profile.grammar_ability,
        "vocabulary_ability": learner_profile.vocabulary_ability, "engagement_score": learner_profile.engagement_score,
        "interests": interests,
    }
    messages = build_recommendation_prompt(learner_summary=learner_summary, candidates=candidates[:top_n])
    llm_messages = [LLMMessage(role=m["role"], content=m["content"]) for m in messages]
    result, usage = await provider.structured(llm_messages, RecommendationOutput, tier=ModelTier.FAST, max_tokens=600)
    ai_usage_service.log(db, user_id=learner_profile.user_id, session_id=None, node="recommendation_engine", usage=usage, tier=ModelTier.FAST)

    now = datetime.now(timezone.utc)
    created = []
    for i, item in enumerate(result.items[:top_n]):
        candidate = candidates[i] if i < len(candidates) else candidates[0]
        skill_id = None
        if candidate.get("target_skill_code"):
            skill_row = await db.execute(select(Skill).where(Skill.code == candidate["target_skill_code"]))
            skill_obj = skill_row.scalar_one_or_none()
            skill_id = skill_obj.id if skill_obj else None

        rec = LearningRecommendation(
            learner_profile_id=learner_profile.id, activity_type=item.activity_type, title=item.title,
            reason_code=candidate["reason_code"], reason_summary=item.reason_summary, target_skill_id=skill_id,
            priority_score=candidate["priority_score"], estimated_minutes=item.estimated_minutes, generated_at=now,
        )
        db.add(rec)
        created.append(rec)

    if created:
        event_service.emit(
            db, event_type=event_service.RECOMMENDATION_GENERATED, user_id=learner_profile.user_id,
            payload={"count": len(created), "activity_types": [r.activity_type for r in created]},
        )
    await db.commit()
    return created
