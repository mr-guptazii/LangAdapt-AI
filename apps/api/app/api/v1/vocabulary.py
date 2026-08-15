from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_learner_profile
from app.database.session import get_db
from app.models.learner import LearnerProfile
from app.models.user import User
from app.models.vocabulary import VocabularyItem
from app.schemas.api import VocabularyItemResponse, VocabularyReviewRequest
from app.services import vocabulary_service

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])


@router.get("", response_model=list[VocabularyItemResponse])
async def list_items(status_filter: str | None = None, learner_profile: LearnerProfile = Depends(get_learner_profile), db: AsyncSession = Depends(get_db)):
    items = await vocabulary_service.list_vocabulary(db, learner_profile_id=learner_profile.id, status=status_filter)
    return items


@router.get("/due", response_model=list[VocabularyItemResponse])
async def due(learner_profile: LearnerProfile = Depends(get_learner_profile), db: AsyncSession = Depends(get_db)):
    return await vocabulary_service.due_for_review(db, learner_profile_id=learner_profile.id)


@router.post("/review")
async def review(
    payload: VocabularyReviewRequest, user: User = Depends(get_current_user),
    learner_profile: LearnerProfile = Depends(get_learner_profile), db: AsyncSession = Depends(get_db),
):
    item = await db.get(VocabularyItem, payload.vocabulary_item_id)
    if item is None or item.learner_profile_id != learner_profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vocabulary item not found.")
    updated = await vocabulary_service.record_review(
        db, item=item, recalled_correctly=payload.recalled_correctly, response_time_ms=payload.response_time_ms, user_id=user.id,
    )
    return {"status": updated.status, "next_review_at": updated.next_review_at.isoformat() if updated.next_review_at else None}
