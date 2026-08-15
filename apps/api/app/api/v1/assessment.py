from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database.session import get_db
from app.models.assessment import AssessmentQuestion, AssessmentSession
from app.models.user import User
from app.schemas.api import AssessmentProgressResponse, StartAssessmentResponse, SubmitAssessmentAnswerRequest
from app.services import assessment_service

router = APIRouter(prefix="/assessment", tags=["assessment"])


def _question_dict(q: AssessmentQuestion) -> dict:
    return {"id": str(q.id), "skill_area": q.skill_area, "difficulty": q.difficulty, "prompt": q.prompt, "options": q.options}


@router.post("/start", response_model=StartAssessmentResponse)
async def start(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    session, question = await assessment_service.start_assessment(db, user_id=user.id)
    return StartAssessmentResponse(assessment_session_id=session.id, question=_question_dict(question))


@router.post("/{assessment_session_id}/answer", response_model=AssessmentProgressResponse)
async def answer(
    assessment_session_id: str, payload: SubmitAssessmentAnswerRequest,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    session = await db.get(AssessmentSession, assessment_session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment session not found.")
    question = await db.get(AssessmentQuestion, payload.question_id)
    if question is None or question.assessment_session_id != session.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found.")

    _is_correct, next_question, result = await assessment_service.submit_answer(
        db, session=session, question=question, answer=payload.answer, user_id=user.id
    )

    if result is not None:
        # Fold the placement result into the learner profile so it becomes the calibrated starting point.
        from app.models.learner import LearnerProfile
        profile_result = await db.execute(select(LearnerProfile).where(LearnerProfile.user_id == user.id))
        profile = profile_result.scalar_one_or_none()
        if profile:
            profile.cefr_level = result["cefr_level"]
            profile.current_difficulty = result["cefr_level"]
            profile.proficiency_confidence = 0.7
            await db.commit()
        return AssessmentProgressResponse(completed=True, result=result)

    return AssessmentProgressResponse(completed=False, next_question=_question_dict(next_question))
