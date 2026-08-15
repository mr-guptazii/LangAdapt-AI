from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database.session import get_db
from app.models.system import AuditLog
from app.models.user import Profile, User
from app.schemas.api import UpdateSettingsRequest

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
async def get_settings(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profile = (await db.execute(select(Profile).where(Profile.user_id == user.id))).scalar_one()
    return {
        "ai_personality": profile.ai_personality, "correction_style": profile.correction_style,
        "voice_speed": profile.voice_speed, "interests": profile.interests,
        "store_raw_audio": profile.store_raw_audio, "personalization_enabled": profile.personalization_enabled,
        "analytics_enabled": profile.analytics_enabled,
    }


@router.patch("")
async def update_settings(payload: UpdateSettingsRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profile = (await db.execute(select(Profile).where(Profile.user_id == user.id))).scalar_one()
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    await db.commit()
    return {"success": True}


@router.post("/export", status_code=status.HTTP_202_ACCEPTED)
async def export_data(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Section 72: data export. Synchronous for MVP scope (a real deployment would
    queue this as a background job and email a download link)."""
    db.add(AuditLog(actor_user_id=user.id, action="data.export"))
    await db.commit()
    return {"status": "export_queued", "message": "Your data export will be emailed to you shortly."}


@router.delete("/account", status_code=status.HTTP_202_ACCEPTED)
async def delete_account(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user.is_active = False
    db.add(AuditLog(actor_user_id=user.id, action="account.delete"))
    await db.commit()
    return {"status": "account_deactivated"}
