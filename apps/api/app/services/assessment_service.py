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
from app.core.logging import get_logger
from app.learning.curriculum import CEFR_ORDER
from app.models.assessment import AssessmentAnswer, AssessmentQuestion, AssessmentSession
from app.schemas.agent_io import GeneratedExercise
from app.services import ai_usage_service, event_service

logger = get_logger(__name__)

SKILL_AREAS = ["vocabulary", "grammar", "reading", "listening", "writing", "speaking"]
DIFFICULTY_STEP = 0.18  # ability move per answer, tapering as question count grows

# These skill areas are always multiple_choice per build_assessment_question_prompt
# (only "writing"/"speaking" are free_response) — used to detect when the FAST-tier
# model (a small model, chosen for cost) ignores that instruction. Observed live: a
# "grammar" question came back as an unrelated free-response prompt with no options
# at all ("What is the correct time to go to bed every night?").
_MULTIPLE_CHOICE_SKILLS = {"vocabulary", "grammar", "reading", "listening"}

# reading/listening are the two skill areas whose guidance requires an actual
# passage followed by a question about it — unlike grammar's fill-in-the-blank
# style ("I go to school every day at_____."), which is a valid prompt with no
# "?" at all. Observed live even after strengthening the prompt: the model
# sometimes writes the passage and stops, never asking anything about it.
_MUST_CONTAIN_QUESTION_MARK = {"reading", "listening"}

# Last-resort fallback if BOTH the FAST and STRONG attempts below fail
# (observed live: the same provider-flake pattern already fixed elsewhere in
# this codebase) — assessment is a multi-question session a learner is mid-way
# through, so losing a question outright breaks the whole onboarding flow,
# unlike a single conversational turn. Always English-language content
# regardless of target language (same limitation as mock_provider.py's
# _MOCK_ASSESSMENT_BANK) — an imperfect question the assessment can still
# score beats a crashed onboarding flow.
_FALLBACK_QUESTIONS: dict[str, dict] = {
    "vocabulary": {
        "prompt": "Which word means 'to obtain something'?",
        "options": ["achieve", "negotiate", "reliable", "deadline"], "correct_answer": "achieve",
    },
    "grammar": {
        "prompt": "Choose the grammatically correct sentence.",
        "options": ["She go to work every day.", "She goes to work every day.",
                    "She going to work every day.", "She gone to work every day."],
        "correct_answer": "She goes to work every day.",
    },
    "reading": {
        "prompt": "\"After the meeting, Sam felt relieved.\" How did Sam feel?",
        "options": ["Anxious", "Relieved", "Confused", "Excited"], "correct_answer": "Relieved",
    },
    "listening": {
        "prompt": "The speaker says: \"I'll meet you at the station at noon.\" What time will they meet?",
        "options": ["9 AM", "Noon", "6 PM", "Midnight"], "correct_answer": "Noon",
    },
    "writing": {
        "prompt": "Write 2-3 sentences describing your favorite hobby.", "options": None,
        "correct_answer": "A grammatically coherent 2-3 sentence response describing a hobby.",
    },
    "speaking": {
        "prompt": "Describe your typical morning routine in a few sentences.", "options": None,
        "correct_answer": "A fluent description of a morning routine.",
    },
}

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
    try:
        result, usage = await provider.structured(llm_messages, GeneratedExercise, tier=tier, max_tokens=400)

        bad_options = skill_area in _MULTIPLE_CHOICE_SKILLS and (not result.options or len(result.options) != 4)
        bad_missing_question = skill_area in _MUST_CONTAIN_QUESTION_MARK and "?" not in result.prompt
        if bad_options or bad_missing_question:
            # Retry once against the larger STRONG-tier model rather than accepting a
            # structurally broken question — no options to render, a wrong option count
            # (observed live: 7 options for one "reading" question, several of them
            # independently true statements, making the correct answer ambiguous), or a
            # reading/listening passage with no actual question asked about it (observed
            # live even after strengthening the prompt to explicitly require one). Cheap
            # insurance since this only fires on a real failure, not every call.
            tier = ModelTier.STRONG
            result, usage = await provider.structured(llm_messages, GeneratedExercise, tier=tier, max_tokens=400)
        ai_usage_service.log(db, user_id=user_id, session_id=None, node="assessment_question_generator", usage=usage, tier=tier)
        prompt, options, correct_answer = result.prompt, result.options, result.correct_answer
    except Exception:
        # Both tiers failed outright (see _FALLBACK_QUESTIONS above) — this is a
        # multi-question session already in progress, so losing a question here
        # would break onboarding entirely rather than just degrading one turn.
        logger.warning("assessment_question_generator_failed_degrading_gracefully", skill_area=skill_area, exc_info=True)
        fallback = _FALLBACK_QUESTIONS[skill_area]
        prompt, options, correct_answer = fallback["prompt"], fallback["options"], fallback["correct_answer"]

    question = AssessmentQuestion(
        assessment_session_id=session.id, order_index=order_index, skill_area=skill_area, difficulty=difficulty,
        prompt=prompt, options=options, correct_answer=correct_answer,
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


def _confidence_from_answer_stability(answers: list[AssessmentAnswer]) -> float:
    """How consistent the learner's correct/incorrect pattern was, in the order
    answered. A learner who flips between right and wrong on every question gives
    a noisier signal for "where is their true level" than one whose results settle
    into a consistent band — so fewer flips means we should trust the final
    ability estimate more. This was previously `0.5 - abs(0.5 - len(answers)/16)`,
    which is degenerate: QUESTIONS_PER_SESSION is a fixed 8, so that formula always
    evaluated to exactly 0.5 for every learner regardless of how they actually
    answered — a constant disguised as a computation."""
    ordered = sorted(answers, key=lambda a: a.answered_at)
    if len(ordered) < 2:
        return 0.5
    flips = sum(1 for i in range(1, len(ordered)) if ordered[i].is_correct != ordered[i - 1].is_correct)
    stability = 1 - (flips / (len(ordered) - 1))
    return round(0.4 + 0.5 * stability, 2)  # floor 0.4 (never fully discount a real result), ceiling 0.9


async def _finalize_assessment(db: AsyncSession, session: AssessmentSession, answers: list[AssessmentAnswer]) -> dict:
    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    session.result_cefr_level = _difficulty_for_ability(session.current_ability_estimate)
    session.result_confidence_interval = _confidence_from_answer_stability(answers)

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
