"""Database seed script (section 61-63). Populates:
  - supported languages + the English curriculum skill set
  - a demo account (demo@lingoadapt.ai / demo1234) at B1 with realistic historical
    weaknesses (past tense, articles, prepositions) and strengths (vocabulary),
    including several backdated sessions/errors/mastery rows so the dashboard,
    mistakes page, and progress charts look populated on first run (section 117:
    no static fake dashboards — these are real rows).

Run with: python scripts/seed.py  (from apps/api, with the venv active)
"""
import asyncio
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import hash_password
from app.database.session import AsyncSessionLocal
from app.learning.curriculum import get_curriculum
from app.models.errors import ErrorOccurrence, LearnerError
from app.models.language import Language, Skill
from app.models.learner import LearnerProfile, LearningGoal, LearningPreference
from app.models.mastery import SkillMastery
from app.models.recommendation import LearningRecommendation
from app.models.session import LearningSession, Message
from app.models.user import Profile, User
from app.models.vocabulary import VocabularyItem

LANGUAGES = [
    ("en", "English", "English"), ("es", "Spanish", "Español"), ("fr", "French", "Français"),
    ("de", "German", "Deutsch"), ("it", "Italian", "Italiano"), ("pt", "Portuguese", "Português"),
    ("ja", "Japanese", "日本語"), ("zh", "Mandarin Chinese", "中文"),
]

DEMO_VOCAB = [
    ("negotiate", "negociar", "verb", "We need to negotiate a better price."),
    ("deadline", "fecha límite", "noun", "The deadline for the project is Friday."),
    ("achieve", "lograr", "verb", "She worked hard to achieve her goals."),
    ("colleague", "colega", "noun", "My colleague helped me finish the report."),
    ("efficient", "eficiente", "adjective", "This is a more efficient way to work."),
    ("opportunity", "oportunidad", "noun", "This job is a great opportunity."),
    ("reliable", "confiable", "adjective", "He is a reliable friend."),
    ("improve", "mejorar", "verb", "I want to improve my speaking skills."),
]


async def seed():
    async with AsyncSessionLocal() as db:
        print("Seeding languages...")
        for code, name, native in LANGUAGES:
            existing = await db.execute(select(Language).where(Language.code == code))
            if existing.scalar_one_or_none() is None:
                db.add(Language(code=code, name=name, native_name=native, supports_learning_engine=(code == "en")))
        await db.commit()

        print("Seeding English curriculum skills...")
        skill_by_code: dict[str, Skill] = {}
        for skill_data in get_curriculum("en"):
            existing = await db.execute(select(Skill).where(Skill.language_code == "en", Skill.code == skill_data["code"]))
            skill = existing.scalar_one_or_none()
            if skill is None:
                skill = Skill(language_code="en", **skill_data)
                db.add(skill)
                await db.flush()
            skill_by_code[skill_data["code"]] = skill
        await db.commit()

        print("Seeding demo user...")
        existing_user = await db.execute(select(User).where(User.email == "demo@lingoadapt.ai"))
        demo_user = existing_user.scalar_one_or_none()
        if demo_user is None:
            demo_user = User(
                email="demo@lingoadapt.ai", hashed_password=hash_password("demo1234"),
                full_name="Demo Learner", is_demo=True, onboarding_completed=True,
            )
            db.add(demo_user)
            await db.flush()
            db.add(Profile(user_id=demo_user.id, display_name="Demo Learner", ai_personality="encouraging",
                            correction_style="balanced", interests=["technology", "travel", "movies"]))

            profile = LearnerProfile(
                user_id=demo_user.id, native_language_code="hi", target_language_code="en",
                cefr_level="B1", proficiency_confidence=0.75,
                grammar_ability=0.52, vocabulary_ability=0.78, speaking_ability=0.58, listening_ability=0.66,
                reading_ability=0.71, writing_ability=0.6, pronunciation_ability=0.6, fluency_ability=0.55,
                confidence_score=0.6, consistency_score=0.65, engagement_score=0.8, learning_speed=0.55,
                current_difficulty="B1", streak_days=6, total_study_minutes=340,
            )
            db.add(profile)
            await db.flush()

            db.add(LearningGoal(learner_profile_id=profile.id, goal_type="career", priority=1))
            db.add(LearningGoal(learner_profile_id=profile.id, goal_type="travel", priority=2))
            db.add(LearningPreference(
                learner_profile_id=profile.id, conversation_affinity=0.75, quiz_affinity=0.35,
                reading_affinity=0.5, listening_affinity=0.55, preferred_explanation_length="short",
                example_preference=0.7, repetition_preference=0.6, challenge_tolerance=0.55,
                correction_style="balanced", preferred_pace="medium",
                interests=["technology", "travel", "movies"], preferred_topics=["technology", "travel"],
                evidence={"conversation_affinity": ["completed 14/16 conversation sessions vs. 3/9 quiz sessions"]},
            ))

            # Weaknesses: past_tense (strong weakness), articles, prepositions. Strength: vocabulary_range.
            now = datetime.now(timezone.utc)
            weak_skills = {"past_tense": 0.38, "articles": 0.45, "prepositions": 0.5}
            strong_skills = {"vocabulary_range": 0.82, "present_simple": 0.88, "pronouns": 0.9}
            for code, mastery in {**weak_skills, **strong_skills}.items():
                skill = skill_by_code.get(code)
                if not skill:
                    continue
                db.add(SkillMastery(
                    learner_profile_id=profile.id, skill_id=skill.id, mastery=mastery, attempts=12, correct_attempts=int(12 * mastery),
                    ease=2.3, interval_days=3, repetitions=3, last_reviewed_at=now - timedelta(days=2),
                    next_review_at=now + timedelta(days=1) if mastery < 0.6 else now + timedelta(days=8),
                    retention_estimate=0.8,
                ))

            # Historical sessions + recurring past-tense mistakes (section 63 demo scenario).
            mistake_examples = [
                ("I go to market yesterday and buy some fruits.", "go", "went", "session 1"),
                ("Yesterday I go to Delhi.", "go", "went", "session 3"),
                ("I have go to the office yesterday.", "go", "went", "session 5"),
            ]
            learner_error = LearnerError(
                learner_profile_id=profile.id, skill_id=skill_by_code["past_tense"].id, error_type="grammar",
                category="past_tense", description="Uses present-tense verb forms ('go', 'have go') when describing past events.",
                occurrence_count=len(mistake_examples), severity="medium", weakness_score=0.62,
                first_seen_at=now - timedelta(days=12), last_seen_at=now - timedelta(days=2), trend="improving",
            )
            db.add(learner_error)
            await db.flush()
            for _text, wrong, right, _label in mistake_examples:
                db.add(ErrorOccurrence(
                    learner_error_id=learner_error.id, incorrect_text=wrong, correct_text=right,
                    explanation=f"'{wrong}' should be '{right}' because the sentence describes a completed past action.",
                    confidence=0.93,
                ))

            for i, (mode, minutes_ago) in enumerate([("conversation", 2), ("grammar", 5), ("conversation", 9), ("vocabulary", 14)]):
                started = now - timedelta(days=minutes_ago)
                session = LearningSession(
                    user_id=demo_user.id, mode=mode, difficulty="B1", started_at=started,
                    ended_at=started + timedelta(minutes=12), duration_seconds=720, score=round(random.uniform(0.6, 0.9), 2), is_active=False,
                )
                db.add(session)
                await db.flush()
                if mode == "conversation":
                    db.add(Message(session_id=session.id, role="user", content=mistake_examples[min(i, 2)][0], input_mode="text"))
                    db.add(Message(session_id=session.id, role="assistant", content="Nice! What did you buy at the market?",
                                    correction_needed=True, correction_priority="medium", teaching_intent="past_tense_practice"))

            for word, translation, pos, example in DEMO_VOCAB:
                status = random.choice(["mastered", "active", "active", "learning"])
                db.add(VocabularyItem(
                    learner_profile_id=profile.id, word=word, translation=translation, part_of_speech=pos,
                    example_sentence=example, category="general", status=status, ease=2.4, interval_days=4,
                    repetitions=3, last_reviewed_at=now - timedelta(days=1), next_review_at=now + timedelta(days=random.randint(-1, 5)),
                ))

            db.add(LearningRecommendation(
                learner_profile_id=profile.id, activity_type="grammar", title="Practice past tense in conversation",
                reason_code="recent_mistake", reason_summary="You've made past-tense mistakes in 3 of your last 5 sessions — a short guided drill will help it stick.",
                target_skill_id=skill_by_code["past_tense"].id, priority_score=0.88, estimated_minutes=8, generated_at=now, status="pending",
            ))
            db.add(LearningRecommendation(
                learner_profile_id=profile.id, activity_type="vocabulary", title="Review 8 vocabulary words",
                reason_code="due_review", reason_summary="8 words are due for spaced-repetition review today.",
                priority_score=0.6, estimated_minutes=5, generated_at=now, status="pending",
            ))
            db.add(LearningRecommendation(
                learner_profile_id=profile.id, activity_type="conversation", title="Talk about your favorite technology",
                reason_code="goal_alignment", reason_summary="Matches your career goal and technology interest, and keeps up your conversation streak.",
                priority_score=0.5, estimated_minutes=7, generated_at=now, status="pending",
            ))

            await db.commit()
            print("Demo user created: demo@lingoadapt.ai / demo1234")
        else:
            print("Demo user already exists, skipping.")

        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
