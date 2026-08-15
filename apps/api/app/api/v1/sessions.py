from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database.session import get_db
from app.models.learner import LearnerProfile
from app.models.session import LearningSession, Message
from app.models.user import User
from app.services import event_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(limit: int = 20, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(LearningSession).where(LearningSession.user_id == user.id).order_by(LearningSession.started_at.desc()).limit(limit)
    )).scalars().all()
    return [{
        "id": str(s.id), "mode": s.mode, "started_at": s.started_at.isoformat(),
        "ended_at": s.ended_at.isoformat() if s.ended_at else None, "score": s.score, "is_active": s.is_active,
    } for s in rows]


@router.get("/{session_id}/messages")
async def get_messages(session_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    session = await db.get(LearningSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    rows = (await db.execute(select(Message).where(Message.session_id == session_id).order_by(Message.created_at.asc()))).scalars().all()
    return [{"id": str(m.id), "role": m.role, "content": m.content, "correction_needed": m.correction_needed, "created_at": m.created_at.isoformat()} for m in rows]


@router.post("/{session_id}/end")
async def end_session(session_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    session = await db.get(LearningSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    now = datetime.now(timezone.utc)
    session.ended_at = now
    session.is_active = False
    session.duration_seconds = int((now - session.started_at).total_seconds())

    # Real, not-hardcoded study-time and streak bookkeeping (section 24/53) —
    # updates the exact numbers the dashboard reads, driven by actual sessions.
    profile_result = await db.execute(select(LearnerProfile).where(LearnerProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if profile:
        profile.total_study_minutes += max(0, session.duration_seconds // 60)
        today = now.date()
        last_active = datetime.fromisoformat(profile.last_active_at).date() if profile.last_active_at else None
        if last_active == today:
            pass  # already counted today
        elif last_active == today - timedelta(days=1):
            profile.streak_days += 1
        else:
            profile.streak_days = 1
        profile.last_active_at = now.isoformat()

    event_type = event_service.CONVERSATION_COMPLETED if session.mode == "conversation" else event_service.LESSON_COMPLETED
    event_service.emit(db, event_type=event_type, user_id=user.id, session_id=session.id, payload={"mode": session.mode, "duration_seconds": session.duration_seconds})

    await db.commit()
    return {"status": "ended", "duration_seconds": session.duration_seconds}
