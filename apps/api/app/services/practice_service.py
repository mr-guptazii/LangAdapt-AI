"""Practice Generator Agent + attempt grading (section 12).

Generation is provenance-tracked: every question carries source_error_id or
source_skill_id back to WHY it was generated. A simple content-hash fingerprint
prevents near-duplicate questions being served repeatedly (section 88).
"""
import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts.practice_generator import build_practice_generation_prompt
from app.ai.providers.base import LLMMessage, ModelTier
from app.ai.providers.factory import get_llm_provider
from app.learning.mastery import update_mastery
from app.learning.spaced_repetition import ScheduleState, quality_from_correctness, update_schedule
from app.models.errors import LearnerError
from app.models.language import Skill
from app.models.learner import LearnerProfile
from app.models.practice import PracticeAttempt, PracticeQuestion
from app.schemas.agent_io import PracticeGenerationOutput
from app.services import ai_usage_service, event_service
from app.tools import learner_tools


def _fingerprint(prompt: str) -> str:
    return hashlib.sha256(prompt.strip().lower().encode()).hexdigest()[:32]


async def generate_practice_for_weakness(
    db: AsyncSession, *, learner_profile: LearnerProfile, skill: Skill, count: int = 3, user_id: UUID | None = None
) -> list[PracticeQuestion]:
    provider = get_llm_provider()

    errors_result = await db.execute(
        select(LearnerError)
        .where(LearnerError.learner_profile_id == learner_profile.id, LearnerError.category == skill.code)
        .order_by(LearnerError.last_seen_at.desc())
        .limit(3)
    )
    source_error = errors_result.scalars().first()
    error_examples = [source_error.description] if source_error else []

    messages = build_practice_generation_prompt(
        target_language=learner_profile.target_language_code,
        cefr_level=learner_profile.cefr_level,
        skill_name=skill.name,
        skill_description=skill.description or skill.name,
        error_examples=error_examples,
        question_types=["multiple_choice", "fill_blank", "correction", "transformation"],
        count=count,
    )
    llm_messages = [LLMMessage(role=m["role"], content=m["content"]) for m in messages]
    result, usage = await provider.structured(llm_messages, PracticeGenerationOutput, tier=ModelTier.FAST, max_tokens=1200)
    ai_usage_service.log(db, user_id=user_id, session_id=None, node="practice_generator", usage=usage, tier=ModelTier.FAST)

    # Anti-repetition: skip near-duplicates already in this learner's recent question set.
    existing_fps = set((await db.execute(
        select(PracticeQuestion.fingerprint).where(PracticeQuestion.for_learner_profile_id == learner_profile.id)
    )).scalars().all())

    created: list[PracticeQuestion] = []
    for ex in result.exercises:
        fp = _fingerprint(ex.prompt)
        if fp in existing_fps:
            continue
        q = PracticeQuestion(
            skill_id=skill.id, source_error_id=source_error.id if source_error else None, source_skill_id=skill.id,
            for_learner_profile_id=learner_profile.id, question_type=ex.question_type, difficulty=learner_profile.cefr_level,
            prompt=ex.prompt, options=ex.options, correct_answer=ex.correct_answer, explanation=ex.explanation,
            fingerprint=fp, validated=True,
        )
        db.add(q)
        created.append(q)
        existing_fps.add(fp)
    await db.flush()
    return created


async def submit_attempt(
    db: AsyncSession, *, learner_profile: LearnerProfile, question: PracticeQuestion, user_id: UUID,
    answer: str, response_time_ms: int, session_id: UUID | None,
) -> tuple[bool, float | None, float | None]:
    is_correct = answer.strip().lower() == question.correct_answer.strip().lower()

    db.add(PracticeAttempt(
        user_id=user_id, question_id=question.id, session_id=session_id, user_answer=answer,
        is_correct=is_correct, response_time_ms=response_time_ms, attempted_at=datetime.now(timezone.utc),
    ))

    new_mastery = delta = None
    skill_id = question.skill_id or question.source_skill_id
    if skill_id:
        mastery_row = await learner_tools.get_or_create_skill_mastery(db, learner_profile.id, skill_id)
        result = update_mastery(current_mastery=mastery_row.mastery, is_correct=is_correct, difficulty=question.difficulty)
        mastery_row.mastery = result.new_mastery
        mastery_row.attempts += 1
        mastery_row.correct_attempts += 1 if is_correct else 0

        schedule = update_schedule(
            ScheduleState(ease=mastery_row.ease, interval_days=mastery_row.interval_days,
                          repetitions=mastery_row.repetitions, retention_estimate=mastery_row.retention_estimate),
            quality=quality_from_correctness(is_correct, response_time_ms),
        )
        mastery_row.ease, mastery_row.interval_days = schedule.ease, schedule.interval_days
        mastery_row.repetitions, mastery_row.retention_estimate = schedule.repetitions, schedule.retention_estimate
        mastery_row.last_reviewed_at = datetime.now(timezone.utc)
        mastery_row.next_review_at = schedule.next_review_at
        new_mastery, delta = result.new_mastery, result.delta

    event_service.emit(
        db, event_type=event_service.QUESTION_ANSWERED if is_correct else event_service.QUESTION_FAILED,
        user_id=user_id, session_id=session_id,
        payload={"question_id": str(question.id), "question_type": question.question_type, "response_time_ms": response_time_ms},
    )

    await db.commit()
    return is_correct, new_mastery, delta
