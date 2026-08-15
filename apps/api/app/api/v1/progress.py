from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_learner_profile
from app.database.session import get_db
from app.models.learner import LearnerProfile
from app.models.user import User
from app.services import progress_service

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/dashboard")
async def dashboard(user: User = Depends(get_current_user), learner_profile: LearnerProfile = Depends(get_learner_profile), db: AsyncSession = Depends(get_db)):
    return await progress_service.get_dashboard_summary(db, learner_profile=learner_profile, user_id=user.id)


@router.get("/mastery")
async def mastery(learner_profile: LearnerProfile = Depends(get_learner_profile), db: AsyncSession = Depends(get_db)):
    return await progress_service.get_mastery_history(db, learner_profile_id=learner_profile.id)


@router.get("/accuracy-trend")
async def accuracy_trend(days: int = 14, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await progress_service.get_practice_accuracy_trend(db, user_id=user.id, days=days)


@router.get("/activity")
async def activity(days: int = 30, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await progress_service.get_activity_summary(db, user_id=user.id, days=days)
