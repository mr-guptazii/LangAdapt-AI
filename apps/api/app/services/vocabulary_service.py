from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.learning.spaced_repetition import ScheduleState, quality_from_correctness, update_schedule
from app.models.vocabulary import VocabularyItem, VocabularyReview
from app.services import event_service


async def list_vocabulary(db: AsyncSession, *, learner_profile_id: UUID, status: str | None = None) -> list[VocabularyItem]:
    stmt = select(VocabularyItem).where(VocabularyItem.learner_profile_id == learner_profile_id)
    if status:
        stmt = stmt.where(VocabularyItem.status == status)
    result = await db.execute(stmt.order_by(VocabularyItem.next_review_at.asc().nulls_last()))
    return list(result.scalars().all())


async def due_for_review(db: AsyncSession, *, learner_profile_id: UUID, limit: int = 20) -> list[VocabularyItem]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(VocabularyItem)
        .where(VocabularyItem.learner_profile_id == learner_profile_id,
               VocabularyItem.next_review_at.is_not(None), VocabularyItem.next_review_at <= now)
        .order_by(VocabularyItem.next_review_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def record_review(
    db: AsyncSession, *, item: VocabularyItem, recalled_correctly: bool, response_time_ms: int, user_id: UUID | None = None
) -> VocabularyItem:
    schedule = update_schedule(
        ScheduleState(ease=item.ease, interval_days=item.interval_days, repetitions=item.repetitions, retention_estimate=1.0),
        quality=quality_from_correctness(recalled_correctly, response_time_ms),
    )
    item.ease, item.interval_days, item.repetitions = schedule.ease, schedule.interval_days, schedule.repetitions
    item.last_reviewed_at = datetime.now(timezone.utc)
    item.next_review_at = schedule.next_review_at

    was_mastered = item.status == "mastered"
    if recalled_correctly and item.repetitions >= 5:
        item.status = "mastered"
    elif recalled_correctly:
        item.status = "active"
    elif not recalled_correctly and item.status == "mastered":
        item.status = "learning"

    db.add(VocabularyReview(
        vocabulary_item_id=item.id, reviewed_at=datetime.now(timezone.utc),
        recalled_correctly=recalled_correctly, response_time_ms=response_time_ms,
    ))
    event_service.emit(
        db, event_type=event_service.VOCABULARY_REVIEWED, user_id=user_id,
        payload={"word": item.word, "recalled_correctly": recalled_correctly},
    )
    if item.status == "mastered" and not was_mastered:
        event_service.emit(db, event_type=event_service.VOCABULARY_LEARNED, user_id=user_id, payload={"word": item.word})
    await db.commit()
    return item
