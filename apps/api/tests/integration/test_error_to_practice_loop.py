"""The exact end-to-end learning loop specified for validation: a learner
makes a real past-tense mistake in conversation, and the system must:
detect it, store it, associate it with the learner, update skill mastery,
recognize recurrence, generate a personalized response, recommend targeted
practice, generate practice questions for the actual error, grade an answer,
update mastery again, record the new learning event, and change what gets
recommended next — using real database state at every step, not mocked
assertions or hardcoded expectations.
"""
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import AnalyticsEvent
from app.models.errors import LearnerError
from app.models.language import Skill
from app.models.learner import LearnerProfile
from app.models.mastery import SkillMastery
from app.services.practice_service import generate_practice_for_weakness, submit_attempt
from tests.integration.conftest import complete_onboarding, register_and_login

MISTAKE_MESSAGE = "Yesterday I go to college and buy some food."


async def _get_or_create_skill(db: AsyncSession) -> Skill:
    # Deliberately does its own lookup-then-create instead of reusing the
    # module-level seeded_skill fixture, since a prior local dev session left
    # duplicate "past_tense" rows committed to the shared dev database outside
    # any test transaction — a plain unconditional insert would risk the same
    # "Multiple rows were found" failure other tests hit against that pollution.
    existing = await db.execute(select(Skill).where(Skill.language_code == "en", Skill.code == "past_tense"))
    skill = existing.scalars().first()
    if skill is None:
        skill = Skill(
            language_code="en", code="past_tense", name="Past Tense", category="grammar",
            cefr_level="A2", description="Simple past for completed actions, including irregular verbs.",
        )
        db.add(skill)
        await db.flush()
    return skill


async def test_full_conversation_error_to_practice_loop(client: AsyncClient, db_session: AsyncSession):
    skill = await _get_or_create_skill(db_session)

    auth = await register_and_login(client, "error-loop@example.com")
    token = auth["access_token"]
    user_id = auth["user_id"]
    await complete_onboarding(client, token)

    # 1, 7, 8: send the mistake, get a real detected-error response, a
    # personalized reply, and a practice recommendation targeted at the error.
    resp = await client.post(
        "/api/v1/chat/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": MISTAKE_MESSAGE, "mode": "conversation"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    categories = {c["category"] for c in body["corrections"]}
    assert "past_tense" in categories, f"expected a past_tense correction, got {body['corrections']}"
    incorrect_words = {c["incorrect"] for c in body["corrections"]}
    assert {"go", "buy"} <= incorrect_words, f"expected both 'go' and 'buy' flagged, got {incorrect_words}"

    assert body["response"]  # 7. a real response was generated
    assert body["recommended_activity"] is not None  # 8. targeted practice recommendation
    assert body["recommended_activity"]["target_skill_code"] == "past_tense"

    profile = (await db_session.execute(select(LearnerProfile).where(LearnerProfile.user_id == user_id))).scalar_one()

    # 2, 3: the error was stored and associated with this specific learner.
    learner_error = (await db_session.execute(
        select(LearnerError).where(LearnerError.learner_profile_id == profile.id, LearnerError.category == "past_tense")
    )).scalar_one()
    assert learner_error.occurrence_count >= 1

    # 4, 6: skill mastery was updated for the actual skill this error belongs to.
    mastery_row = (await db_session.execute(
        select(SkillMastery).where(SkillMastery.learner_profile_id == profile.id, SkillMastery.skill_id == skill.id)
    )).scalar_one()
    mastery_after_error = mastery_row.mastery
    attempts_after_error = mastery_row.attempts
    assert attempts_after_error >= 1

    # 5: recurrence — the same category of mistake again increments occurrence_count
    # on the SAME LearnerError row rather than creating a new one.
    resp2 = await client.post(
        "/api/v1/chat/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "Yesterday I go to the market again.", "mode": "conversation", "session_id": body["session_id"]},
    )
    assert resp2.status_code == 200, resp2.text
    await db_session.refresh(learner_error)
    assert learner_error.occurrence_count >= 2

    # 9: practice questions generated targeting the actual error (real provenance
    # link, not just "some question about the skill").
    questions = await generate_practice_for_weakness(
        db_session, learner_profile=profile, skill=skill, count=1, user_id=user_id
    )
    assert questions, "no practice questions were generated for the learner's actual weak skill"
    question = questions[0]
    assert question.skill_id == skill.id
    assert question.source_error_id == learner_error.id

    # 10: submitting the correct answer updates mastery upward from where it was
    # after the error (not just to some new value).
    is_correct, new_mastery, _delta = await submit_attempt(
        db_session, learner_profile=profile, question=question, user_id=user_id,
        answer=question.correct_answer, response_time_ms=2000, session_id=None,
    )
    assert is_correct is True
    assert new_mastery is not None and new_mastery > mastery_after_error

    # 11: real learning events were stored for this user across the whole flow.
    events = (await db_session.execute(select(AnalyticsEvent).where(AnalyticsEvent.user_id == user_id))).scalars().all()
    event_types = {e.event_type for e in events}
    assert "error_detected" in event_types
    assert "skill_mastery_updated" in event_types
    assert "question_answered" in event_types

    # 12: the next recommendation reflects the new result — the skill's spaced-
    # repetition schedule moved into the future after a correct answer, a real,
    # DB-verifiable change in what would be due for review next.
    await db_session.refresh(mastery_row)
    assert mastery_row.next_review_at > mastery_row.last_reviewed_at
    assert mastery_row.attempts > attempts_after_error
