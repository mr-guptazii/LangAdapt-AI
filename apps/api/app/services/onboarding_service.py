from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learner import LearnerProfile, LearningGoal, LearningPreference
from app.models.user import Profile, User
from app.schemas.api import OnboardingRequest

# A learner's self-estimated level seeds a *starting point* only; the placement
# assessment (app/services/assessment_service.py) is what actually calibrates it.
_LEVEL_TO_ABILITY = {"A1": 0.15, "A2": 0.3, "B1": 0.45, "B2": 0.6, "C1": 0.75, "C2": 0.9}


async def complete_onboarding(db: AsyncSession, *, user: User, payload: OnboardingRequest) -> LearnerProfile:
    starting_ability = _LEVEL_TO_ABILITY.get(payload.self_estimated_level or "A2", 0.3)

    profile = LearnerProfile(
        user_id=user.id,
        native_language_code=payload.native_language_code,
        target_language_code=payload.target_language_code,
        cefr_level=payload.self_estimated_level or "A2",
        proficiency_confidence=0.3,  # low confidence until placement assessment runs
        grammar_ability=starting_ability,
        vocabulary_ability=starting_ability,
        speaking_ability=starting_ability,
        listening_ability=starting_ability,
        reading_ability=starting_ability,
        writing_ability=starting_ability,
        pronunciation_ability=starting_ability,
        fluency_ability=starting_ability,
        current_difficulty=payload.self_estimated_level or "A2",
    )
    db.add(profile)
    await db.flush()

    for goal in payload.goal_types:
        db.add(LearningGoal(learner_profile_id=profile.id, goal_type=goal))

    db.add(LearningPreference(
        learner_profile_id=profile.id,
        correction_style=payload.correction_style,
        interests=payload.interests,
        preferred_topics=payload.interests,
    ))

    user.onboarding_completed = True

    result = await db.execute(select(Profile).where(Profile.user_id == user.id))
    prof_row = result.scalar_one_or_none()
    if prof_row:
        prof_row.ai_personality = payload.ai_personality
        prof_row.correction_style = payload.correction_style
        prof_row.interests = payload.interests

    await db.flush()
    return profile
