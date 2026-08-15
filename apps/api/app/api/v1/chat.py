from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_learner_profile
from app.core.rate_limit import RateLimit
from app.database.session import get_db
from app.models.learner import LearnerProfile
from app.models.user import User
from app.schemas.api import SendMessageRequest, SendMessageResponse
from app.services.chat_service import send_message

router = APIRouter(prefix="/chat", tags=["chat"])

# Per-user cap on LLM-calling turns (section 43: excessive API usage protection).
_chat_limit = RateLimit(times=30, seconds=60, scope="chat_message")


@router.post("/message", response_model=SendMessageResponse, dependencies=[Depends(_chat_limit)])
async def message(
    payload: SendMessageRequest,
    user: User = Depends(get_current_user),
    learner_profile: LearnerProfile = Depends(get_learner_profile),
    db: AsyncSession = Depends(get_db),
):
    return await send_message(db, user_id=user.id, learner_profile=learner_profile, req=payload)
