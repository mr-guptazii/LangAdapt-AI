from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.rate_limit import RateLimit
from app.database.session import get_db
from app.models.user import User
from app.schemas.api import ForgotPasswordRequest, LoginRequest, RegisterRequest, ResetPasswordRequest, TokenResponse
from app.services.auth_service import AuthError, authenticate_user, register_user
from app.services.auth_service import request_password_reset as _request_password_reset
from app.services.auth_service import reset_password as _reset_password

router = APIRouter(prefix="/auth", tags=["auth"])

# Brute-force / abuse protection (section 43, 71) — keyed by client IP since
# these routes run before any auth token exists.
_register_limit = RateLimit(times=5, seconds=3600, scope="auth_register")
_login_limit = RateLimit(times=10, seconds=300, scope="auth_login")
_forgot_password_limit = RateLimit(times=5, seconds=3600, scope="auth_forgot_password")
_reset_password_limit = RateLimit(times=10, seconds=3600, scope="auth_reset_password")


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(_register_limit)])
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        user, token = await register_user(db, email=payload.email, password=payload.password, full_name=payload.full_name)
        await db.commit()
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    return TokenResponse(access_token=token, user_id=user.id, onboarding_completed=user.onboarding_completed)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(_login_limit)])
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        user, token = await authenticate_user(db, email=payload.email, password=payload.password)
        await db.commit()
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    return TokenResponse(access_token=token, user_id=user.id, onboarding_completed=user.onboarding_completed)


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "id": str(user.id), "email": user.email, "full_name": user.full_name,
        "onboarding_completed": user.onboarding_completed, "is_demo": user.is_demo, "is_admin": user.is_admin,
    }


@router.post("/forgot-password", dependencies=[Depends(_forgot_password_limit)])
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Real, secure token generation — but no email transport is configured
    yet (see CLAUDE.md), so a reset link can't actually reach the user's
    inbox on its own. The response is identical whether or not the account
    exists, by design: this is what stops the endpoint from being usable to
    check which emails have accounts."""
    await _request_password_reset(db, email=payload.email)
    await db.commit()
    return {"message": "If an account exists for that email, a password reset has been started."}


@router.post("/reset-password", dependencies=[Depends(_reset_password_limit)])
async def reset_password_endpoint(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    ok = await _reset_password(db, raw_token=payload.token, new_password=payload.new_password)
    await db.commit()
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset link.")
    return {"message": "Password reset successful. You can now log in with your new password."}
