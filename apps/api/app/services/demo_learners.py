"""Two deterministic demo learners used to prove personalization actually
diverges (not just that the fields exist). Shared by scripts/seed_demo_learners.py
and tests/integration/test_personalization_divergence.py so the test exercises
the exact same data a human could inspect via the seed script — no separate
"test-only" fixture drifting from what a demo would show.

DEMO LEARNER A: B1, strong vocabulary, weak past tense, prefers conversation,
prefers short explanations.
DEMO LEARNER B: B1, strong grammar, weak vocabulary, prefers quizzes, prefers
detailed explanations.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.errors import LearnerError
from app.models.language import Skill
from app.models.learner import LearnerProfile, LearningGoal, LearningPreference
from app.models.mastery import SkillMastery
from app.models.user import Profile, User

DEMO_LEARNER_A_EMAIL = "demo-learner-a@lingoadapt.ai"
DEMO_LEARNER_B_EMAIL = "demo-learner-b@lingoadapt.ai"
DEMO_PASSWORD = "demopass123"  # noqa: S105 — a known, published demo credential, not a real secret


async def _get_skill(db: AsyncSession, code: str) -> Skill | None:
    result = await db.execute(select(Skill).where(Skill.language_code == "en", Skill.code == code))
    return result.scalar_one_or_none()


async def _create_learner(
    db: AsyncSession, *, email: str, display_name: str, ai_personality: str, interests: list[str],
    grammar_ability: float, vocabulary_ability: float,
    conversation_affinity: float, quiz_affinity: float, explanation_length: str,
    weak_skill_code: str, weak_mastery: float, strong_skill_code: str, strong_mastery: float,
) -> tuple[User, LearnerProfile]:
    existing = await db.execute(select(User).where(User.email == email))
    user = existing.scalar_one_or_none()
    if user is not None:
        profile_result = await db.execute(select(LearnerProfile).where(LearnerProfile.user_id == user.id))
        return user, profile_result.scalar_one()

    user = User(email=email, hashed_password=hash_password(DEMO_PASSWORD), full_name=display_name, is_demo=True, onboarding_completed=True)
    db.add(user)
    await db.flush()

    db.add(Profile(
        user_id=user.id, display_name=display_name, ai_personality=ai_personality,
        correction_style="balanced", interests=interests, personalization_enabled=True,
    ))

    profile = LearnerProfile(
        user_id=user.id, native_language_code="hi", target_language_code="en",
        cefr_level="B1", proficiency_confidence=0.6,
        grammar_ability=grammar_ability, vocabulary_ability=vocabulary_ability,
        speaking_ability=0.5, listening_ability=0.5, reading_ability=0.5, writing_ability=0.5,
        pronunciation_ability=0.5, fluency_ability=0.5,
        confidence_score=0.5, consistency_score=0.5, engagement_score=0.5, learning_speed=0.5,
        current_difficulty="B1", streak_days=3, total_study_minutes=90,
    )
    db.add(profile)
    await db.flush()

    db.add(LearningGoal(learner_profile_id=profile.id, goal_type="general_fluency", priority=1))
    db.add(LearningPreference(
        learner_profile_id=profile.id, conversation_affinity=conversation_affinity, quiz_affinity=quiz_affinity,
        reading_affinity=0.5, listening_affinity=0.5, preferred_explanation_length=explanation_length,
        example_preference=0.6, repetition_preference=0.5, challenge_tolerance=0.5,
        correction_style="balanced", preferred_pace="medium", interests=interests, preferred_topics=interests,
        evidence={"conversation_affinity" if conversation_affinity > quiz_affinity else "quiz_affinity": ["seeded demo learner profile"]},
    ))

    now = datetime.now(timezone.utc)
    weak_skill = await _get_skill(db, weak_skill_code)
    strong_skill = await _get_skill(db, strong_skill_code)
    if weak_skill:
        db.add(SkillMastery(
            learner_profile_id=profile.id, skill_id=weak_skill.id, mastery=weak_mastery,
            attempts=10, correct_attempts=int(10 * weak_mastery), ease=2.2, interval_days=1, repetitions=1,
            last_reviewed_at=now - timedelta(days=1), next_review_at=now, retention_estimate=0.5,
        ))
        db.add(LearnerError(
            learner_profile_id=profile.id, skill_id=weak_skill.id, error_type="grammar" if weak_skill.category == "grammar" else "vocabulary",
            category=weak_skill_code, description=f"Recurring difficulty with {weak_skill.name.lower()}.",
            occurrence_count=5, severity="medium", weakness_score=0.65,
            first_seen_at=now - timedelta(days=10), last_seen_at=now - timedelta(days=1), trend="stable",
        ))
    if strong_skill:
        db.add(SkillMastery(
            learner_profile_id=profile.id, skill_id=strong_skill.id, mastery=strong_mastery,
            attempts=15, correct_attempts=int(15 * strong_mastery), ease=2.6, interval_days=10, repetitions=5,
            last_reviewed_at=now - timedelta(days=3), next_review_at=now + timedelta(days=7), retention_estimate=0.9,
        ))

    return user, profile


async def create_demo_learner_a(db: AsyncSession) -> tuple[User, LearnerProfile]:
    return await _create_learner(
        db, email=DEMO_LEARNER_A_EMAIL, display_name="Demo Learner A", ai_personality="casual",
        interests=["technology", "travel"],
        grammar_ability=0.4, vocabulary_ability=0.85,
        conversation_affinity=0.85, quiz_affinity=0.25, explanation_length="short",
        weak_skill_code="past_tense", weak_mastery=0.3,
        strong_skill_code="vocabulary_range", strong_mastery=0.85,
    )


async def create_demo_learner_b(db: AsyncSession) -> tuple[User, LearnerProfile]:
    return await _create_learner(
        db, email=DEMO_LEARNER_B_EMAIL, display_name="Demo Learner B", ai_personality="strict_coach",
        interests=["business", "science"],
        grammar_ability=0.85, vocabulary_ability=0.35,
        conversation_affinity=0.25, quiz_affinity=0.85, explanation_length="long",
        weak_skill_code="vocabulary_range", weak_mastery=0.3,
        strong_skill_code="present_perfect", strong_mastery=0.85,
    )
