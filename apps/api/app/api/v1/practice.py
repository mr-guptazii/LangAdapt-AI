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
    if skill_code is None:
        top_error = (await db.execute(
            select(LearnerError).where(LearnerError.learner_profile_id == learner_profile.id)
            .order_by(LearnerError.weakness_score.desc()).limit(1)
        )).scalar_one_or_none()
        skill_code = top_error.category if top_error else "present_simple"

    skill = (await db.execute(
        select(Skill).where(Skill.language_code == learner_profile.target_language_code, Skill.code == skill_code)
    )).scalar_one_or_none()
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
