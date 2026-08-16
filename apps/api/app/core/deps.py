from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.database.session import get_db
from app.models.learner import LearnerProfile
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    request.state.user_id = str(user.id)  # lets RateLimit key by user instead of IP once auth has resolved
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


async def get_learner_profile(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> LearnerProfile:
    """Loads the caller's OWN learner profile. Every learner-data endpoint depends
    on this (never accepts a learner_profile_id from the client) so a user can never
    read another user's learning data — see section 36 (tenant isolation)."""
    result = await db.execute(select(LearnerProfile).where(LearnerProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found. Complete onboarding first.")
    return profile


async def get_learner_profile_optional(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> LearnerProfile | None:
    """Same lookup as get_learner_profile but returns None instead of 404ing —
    for endpoints (e.g. voice transcription) that are also used pre-onboarding,
    during the placement assessment, before a LearnerProfile row exists."""
    result = await db.execute(select(LearnerProfile).where(LearnerProfile.user_id == user.id))
    return result.scalar_one_or_none()


def require_owns(resource_user_id: UUID, user: User) -> None:
    if resource_user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this resource")
