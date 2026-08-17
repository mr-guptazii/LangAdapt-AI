from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_learner_profile
from app.core.rate_limit import RateLimit
from app.database.session import get_db
from app.models.errors import LearnerError
from app.models.language import Skill
from app.models.learner import LearnerProfile
from app.models.practice import PracticeQuestion
from app.models.user import User
from app.schemas.api import PracticeQuestionResponse, SubmitPracticeAnswerRequest, SubmitPracticeAnswerResponse
from app.services import practice_service

router = APIRouter(prefix="/practice", tags=["practice"])

_generate_limit = RateLimit(times=20, seconds=60, scope="practice_generate")


@router.get("/next", response_model=list[PracticeQuestionResponse], dependencies=[Depends(_generate_limit)])
async def next_practice(
    skill_code: str | None = None,
    count: int = 3,
    user: User = Depends(get_current_user),
    learner_profile: LearnerProfile = Depends(get_learner_profile),
    db: AsyncSession = Depends(get_db),
):
    """Generates exercises for the given skill, or the learner's current top
    weakness if no skill_code is provided (section 12: never random when a
    personalized weakness is available)."""
    skill: Skill | None = None

    if skill_code is None:
        # error_analysis_agent's `category` field is LLM-generated free text
        # (see app/ai/prompts/error_analysis.py) — not guaranteed to exactly
        # match one of the curated Skill codes. Observed live: a real error
        # categorized "vocabulary" (the closest real skill code is actually
        # "vocabulary_range") 404'd this endpoint outright on an auto-derived
        # lookup, which is never something the caller did wrong. Walk recent
        # errors by weakness until one actually resolves to a real skill,
        # instead of trusting only the single highest-weakness category.
        top_errors = (await db.execute(
            select(LearnerError).where(LearnerError.learner_profile_id == learner_profile.id)
            .order_by(LearnerError.weakness_score.desc()).limit(5)
        )).scalars().all()
        for err in top_errors:
            # .scalars().first() not .scalar_one_or_none(): Skill.code has no
            # DB-level uniqueness constraint (see app/models/language.py), so a
            # re-run of scripts.seed can leave duplicate rows for the same
            # (language_code, code) — observed live: this exact query raised
            # MultipleResultsFound and 500'd every /practice/next call for one
            # real account, even though every other endpoint using the same
            # learner_profile worked fine (they never query Skill this way).
            skill = (await db.execute(
                select(Skill).where(Skill.language_code == learner_profile.target_language_code, Skill.code == err.category)
            )).scalars().first()
            if skill:
                break
        if skill is None:
            skill_code = "present_simple"  # a real, always-seeded default

    if skill is None:
        skill = (await db.execute(
            select(Skill).where(Skill.language_code == learner_profile.target_language_code, Skill.code == skill_code)
        )).scalars().first()
        if skill is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown skill '{skill_code}' for this language.")

    questions = await practice_service.generate_practice_for_weakness(db, learner_profile=learner_profile, skill=skill, count=count, user_id=user.id)
    await db.commit()
    return [
        PracticeQuestionResponse(id=q.id, question_type=q.question_type, difficulty=q.difficulty, prompt=q.prompt,
                                  options=q.options, source_error_id=q.source_error_id, source_skill_id=q.source_skill_id)
        for q in questions
    ]


@router.post("/submit", response_model=SubmitPracticeAnswerResponse)
async def submit(
    payload: SubmitPracticeAnswerRequest,
    user: User = Depends(get_current_user),
    learner_profile: LearnerProfile = Depends(get_learner_profile),
    db: AsyncSession = Depends(get_db),
):
    question = await db.get(PracticeQuestion, payload.question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found.")
    if question.for_learner_profile_id and question.for_learner_profile_id != learner_profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this question.")

    is_correct, new_mastery, delta = await practice_service.submit_attempt(
        db, learner_profile=learner_profile, question=question, user_id=user.id,
        answer=payload.answer, response_time_ms=payload.response_time_ms, session_id=None,
    )
    return SubmitPracticeAnswerResponse(
        is_correct=is_correct, correct_answer=question.correct_answer, explanation=question.explanation,
        new_mastery=new_mastery, mastery_delta=delta,
    )
