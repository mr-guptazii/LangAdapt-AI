"""'Why this lesson?' AI decision trace (section 32) + raw memory browsing."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_learner_profile
from app.database.session import get_db
from app.models.agent import AgentDecision
from app.models.learner import LearnerProfile
from app.models.memory import LearnerMemory
from app.models.user import User

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/facts")
async def list_memories(learner_profile: LearnerProfile = Depends(get_learner_profile), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(LearnerMemory).where(LearnerMemory.learner_profile_id == learner_profile.id).order_by(LearnerMemory.importance.desc())
    )).scalars().all()
    return [{"id": str(m.id), "type": m.memory_type, "content": m.content, "importance": m.importance, "last_reinforced_at": m.last_reinforced_at.isoformat()} for m in rows]


@router.get("/decisions")
async def list_decisions(limit: int = 10, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Structured, non-chain-of-thought decision trail (section 121) — powers the
    'Why this lesson?' card. Never exposes raw model reasoning."""
    rows = (await db.execute(
        select(AgentDecision).where(AgentDecision.user_id == user.id).order_by(AgentDecision.created_at.desc()).limit(limit)
    )).scalars().all()
    return [{
        "id": str(d.id), "agent_name": d.agent_name, "decision": d.decision, "reason_code": d.reason_code,
        "reason_summary": d.reason_summary, "confidence": d.confidence, "recommended_action": d.recommended_action,
        "created_at": d.created_at.isoformat(),
    } for d in rows]
