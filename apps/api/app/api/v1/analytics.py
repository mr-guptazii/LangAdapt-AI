"""Admin observability endpoints (sections 56-57). Admin never sees private
conversation content here — only aggregate counts (section 56)."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin
from app.database.session import get_db
from app.models.user import User
from app.services import admin_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/admin/overview")
async def admin_overview(_admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await admin_service.get_overview(db)


@router.get("/admin/ai-usage")
async def admin_ai_usage(days: int = 30, _admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await admin_service.get_ai_usage_summary(db, days=days)


@router.get("/admin/common-errors")
async def admin_common_errors(limit: int = 10, _admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await admin_service.get_common_errors(db, limit=limit)


@router.get("/admin/retention")
async def admin_retention(_admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await admin_service.get_retention(db)


@router.get("/admin/system-health")
async def admin_system_health(_admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await admin_service.get_system_health(db)
