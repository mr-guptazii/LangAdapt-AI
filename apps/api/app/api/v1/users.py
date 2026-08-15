from fastapi import APIRouter, Depends

from app.core.deps import get_current_user, get_learner_profile
from app.models.learner import LearnerProfile
from app.models.user import User

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/profile")
async def my_profile(user: User = Depends(get_current_user), learner_profile: LearnerProfile = Depends(get_learner_profile)):
    return {
        "email": user.email,
        "target_language": learner_profile.target_language_code,
        "native_language": learner_profile.native_language_code,
        "cefr_level": learner_profile.cefr_level,
        "streak_days": learner_profile.streak_days,
        "current_difficulty": learner_profile.current_difficulty,
    }
