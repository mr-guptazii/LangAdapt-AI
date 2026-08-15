from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_learner_profile
from app.database.session import get_db
from app.models.learner import LearnerProfile
from app.models.recommendation import LearningRecommendation
from app.services import recommendation_service

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("")
async def get_recommendations(refresh: bool = False, learner_profile: LearnerProfile = Depends(get_learner_profile), db: AsyncSession = Depends(get_db)):
    if not refresh:
        existing = (await db.execute(
            select(LearningRecommendation)
            .where(LearningRecommendation.learner_profile_id == learner_profile.id, LearningRecommendation.status == "pending")
            .order_by(LearningRecommendation.priority_score.desc()).limit(3)
        )).scalars().all()
        if existing:
            return [_dict(r) for r in existing]

    created = await recommendation_service.generate_recommendations(db, learner_profile=learner_profile)
    return [_dict(r) for r in created]


def _dict(r: LearningRecommendation) -> dict:
    return {
        "id": str(r.id), "activity_type": r.activity_type, "title": r.title, "reason_code": r.reason_code,
        "reason_summary": r.reason_summary, "priority_score": r.priority_score, "estimated_minutes": r.estimated_minutes,
        "status": r.status,
    }
