import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPKMixin


class VocabularyItem(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "vocabulary_items"

    learner_profile_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learner_profiles.id", ondelete="CASCADE"), index=True
    )
    word: Mapped[str] = mapped_column(String(128), index=True)
    translation: Mapped[str] = mapped_column(String(256))
    part_of_speech: Mapped[str | None] = mapped_column(String(32), nullable=True)
    example_sentence: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pronunciation_ipa: Mapped[str | None] = mapped_column(String(128), nullable=True)

    status: Mapped[str] = mapped_column(String(16), default="learning")  # learning|active|passive|forgotten|mastered
    times_confused_with: Mapped[list[str]] = mapped_column(JSON, default=list)

    # spaced repetition (shared scheduling approach with SkillMastery)
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[float] = mapped_column(Float, default=0.0)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class VocabularyReview(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "vocabulary_reviews"

    vocabulary_item_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("vocabulary_items.id", ondelete="CASCADE"), index=True
    )
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recalled_correctly: Mapped[bool] = mapped_column(Boolean)
    response_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    context: Mapped[str] = mapped_column(String(32), default="flashcard")  # flashcard|conversation|writing|practice
