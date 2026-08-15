from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.api import OnboardingRequest
from app.services.onboarding_service import complete_onboarding

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/complete", status_code=status.HTTP_201_CREATED)
async def complete(payload: OnboardingRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.onboarding_completed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Onboarding already completed.")
    profile = await complete_onboarding(db, user=user, payload=payload)
    await db.commit()
    return {"learner_profile_id": str(profile.id), "cefr_level": profile.cefr_level}
