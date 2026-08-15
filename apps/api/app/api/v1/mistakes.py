"""The 'Your Learning Memory' page backend (section 29)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_learner_profile
from app.database.session import get_db
from app.models.errors import ErrorOccurrence, LearnerError
from app.models.learner import LearnerProfile

router = APIRouter(prefix="/mistakes", tags=["mistakes"])


@router.get("")
async def list_mistakes(learner_profile: LearnerProfile = Depends(get_learner_profile), db: AsyncSession = Depends(get_db)):
    errors = (await db.execute(
        select(LearnerError).where(LearnerError.learner_profile_id == learner_profile.id).order_by(LearnerError.weakness_score.desc())
    )).scalars().all()

    out = []
    for e in errors:
        occurrences = (await db.execute(
            select(ErrorOccurrence).where(ErrorOccurrence.learner_error_id == e.id).order_by(ErrorOccurrence.created_at.desc()).limit(5)
        )).scalars().all()
        out.append({
            "id": str(e.id), "category": e.category, "error_type": e.error_type, "description": e.description,
            "occurrence_count": e.occurrence_count, "weakness_score": e.weakness_score, "severity": e.severity,
            "trend": e.trend, "first_seen_at": e.first_seen_at.isoformat(), "last_seen_at": e.last_seen_at.isoformat(),
            "mastery": round(1 - e.weakness_score, 2),
            "examples": [{"incorrect": o.incorrect_text, "correct": o.correct_text, "explanation": o.explanation} for o in occurrences],
        })
    return out
