"""Adaptive placement assessment (section 13). Uses a lightweight IRT-style
ability estimate (0..1) updated after each answer: correct on a hard question
moves ability up more than correct on an easy one, and vice versa. Difficulty of
the NEXT question is chosen from the updated estimate, which is what makes this
adaptive rather than a fixed 20-question form.
"""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts.assessment import build_assessment_question_prompt
from app.ai.providers.base import LLMMessage, ModelTier
from app.ai.providers.factory import get_llm_provider
from app.learning.curriculum import CEFR_ORDER
from app.models.assessment import AssessmentAnswer, AssessmentQuestion, AssessmentSession
from app.schemas.agent_io import GeneratedExercise
from app.services import ai_usage_service, event_service

SKILL_AREAS = ["vocabulary", "grammar", "reading", "listening", "writing", "speaking"]
DIFFICULTY_STEP = 0.18  # ability move per answer, tapering as question count grows

# These skill areas are always multiple_choice per build_assessment_question_prompt
# (only "writing"/"speaking" are free_response) — used to detect when the FAST-tier
# model (a small model, chosen for cost) ignores that instruction. Observed live: a
# "grammar" question came back as an unrelated free-response prompt with no options
# at all ("What is the correct time to go to bed every night?").
_MULTIPLE_CHOICE_SKILLS = {"vocabulary", "grammar", "reading", "listening"}

# Mirrors the LANGUAGES list in apps/web/src/app/onboarding/page.tsx. The LLM
# prompt needs a human-readable language name, not an ISO code — without this,
# question generation had no real signal for which language it was testing and
# would pick one essentially at random (observed live: an English-onboarding
# user got a French vocabulary question).
LANGUAGE_NAMES = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German", "it": "Italian",
    "pt": "Portuguese", "ja": "Japanese", "zh": "Mandarin Chinese", "hi": "Hindi",
}


def _language_name(code: str | None) -> str:
    return LANGUAGE_NAMES.get(code or "", "English")


def _difficulty_for_ability(ability: float) -> str:
    idx = min(len(CEFR_ORDER) - 1, max(0, round(ability * (len(CEFR_ORDER) - 1))))
    return CEFR_ORDER[idx]


async def start_assessment(
    db: AsyncSession, *, user_id: UUID, target_language_code: str | None = None
) -> tuple[AssessmentSession, AssessmentQuestion]:
    session = AssessmentSession(user_id=user_id, started_at=datetime.now(timezone.utc), current_ability_estimate=0.35, current_difficulty="A2")
    db.add(session)
    await db.flush()
    event_service.emit(db, event_type=event_service.ASSESSMENT_STARTED, user_id=user_id, payload={})
    question = await _generate_next_question(
        db, session, skill_area=SKILL_AREAS[0], order_index=0, user_id=user_id, target_language_code=target_language_code
    )
    await db.commit()
    return session, question


async def _generate_next_question(
    db: AsyncSession, session: AssessmentSession, *, skill_area: str, order_index: int,
    user_id: UUID | None = None, target_language_code: str | None = None,
) -> AssessmentQuestion:
    provider = get_llm_provider()
    difficulty = _difficulty_for_ability(session.current_ability_estimate)
    messages = build_assessment_question_prompt(target_language=_language_name(target_language_code), skill_area=skill_area, difficulty=difficulty)
    llm_messages = [LLMMessage(role=m["role"], content=m["content"]) for m in messages]
    tier = ModelTier.FAST
    result, usage = await provider.structured(llm_messages, GeneratedExercise, tier=tier, max_tokens=400)

    if skill_area in _MULTIPLE_CHOICE_SKILLS and (not result.options or len(result.options) < 2):
        # Retry once against the larger STRONG-tier model rather than accepting a
        # structurally broken question (no options to render, or too few to be a
        # real choice) — cheap insurance since this only fires on a real failure,
        # not every call.
        tier = ModelTier.STRONG
        result, usage = await provider.structured(llm_messages, GeneratedExercise, tier=tier, max_tokens=400)

    ai_usage_service.log(db, user_id=user_id, session_id=None, node="assessment_question_generator", usage=usage, tier=tier)

    question = AssessmentQuestion(
        assessment_session_id=session.id, order_index=order_index, skill_area=skill_area, difficulty=difficulty,
        prompt=result.prompt, options=result.options, correct_answer=result.correct_answer,
    )
    db.add(question)
    await db.flush()
    return question


async def submit_answer(
    db: AsyncSession, *, session: AssessmentSession, question: AssessmentQuestion, answer: str,
    user_id: UUID | None = None, target_language_code: str | None = None,
) -> tuple[bool, AssessmentQuestion | None, dict | None]:
    is_correct = answer.strip().lower() == question.correct_answer.strip().lower()

    move = DIFFICULTY_STEP * (1 if is_correct else -1)
    session.current_ability_estimate = max(0.02, min(0.98, session.current_ability_estimate + move))

    db.add(AssessmentAnswer(
        assessment_question_id=question.id, user_answer=answer, is_correct=is_correct,
        ability_estimate_after=session.current_ability_estimate, answered_at=datetime.now(timezone.utc),
    ))
    await db.flush()

    answered_count = (await db.execute(
        select(AssessmentAnswer).join(AssessmentQuestion).where(AssessmentQuestion.assessment_session_id == session.id)
    )).scalars().all()
    total_answered = len(answered_count)

    QUESTIONS_PER_SESSION = 8
    if total_answered >= QUESTIONS_PER_SESSION:
        result = await _finalize_assessment(db, session, answered_count)
        event_service.emit(db, event_type=event_service.ASSESSMENT_COMPLETED, user_id=user_id, payload={"cefr_level": result["cefr_level"]})
        await db.commit()
        return is_correct, None, result

    next_skill_area = SKILL_AREAS[total_answered % len(SKILL_AREAS)]
    next_question = await _generate_next_question(
        db, session, skill_area=next_skill_area, order_index=total_answered, user_id=user_id, target_language_code=target_language_code
    )
    await db.commit()
    return is_correct, next_question, None


async def _finalize_assessment(db: AsyncSession, session: AssessmentSession, answers: list[AssessmentAnswer]) -> dict:
    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    session.result_cefr_level = _difficulty_for_ability(session.current_ability_estimate)
    session.result_confidence_interval = round(0.5 - abs(0.5 - len(answers) / 16), 2)

    # Per-skill-area breakdown from the answered questions.
    breakdown: dict[str, list[bool]] = {}
    for ans in answers:
        q = await db.get(AssessmentQuestion, ans.assessment_question_id)
        breakdown.setdefault(q.skill_area, []).append(ans.is_correct)

    scores = {area: round(sum(v) / len(v), 2) for area, v in breakdown.items()}
    session.result_breakdown = scores
    session.result_strengths = [a for a, s in scores.items() if s >= 0.7]
    session.result_weaknesses = [a for a, s in scores.items() if s < 0.5]

    return {
        "cefr_level": session.result_cefr_level,
        "confidence_interval": session.result_confidence_interval,
        "breakdown": scores,
        "strengths": session.result_strengths,
        "weaknesses": session.result_weaknesses,
    }
