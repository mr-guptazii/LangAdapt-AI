import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPKMixin


class LearnerError(Base, UUIDPKMixin, TimestampMixin):
    """A recurring error PATTERN for a learner (e.g. 'past_tense: go/went confusion').

    This is the aggregate row the Mistakes page and recommendation engine read.
    Individual instances are recorded in ErrorOccurrence and roll up into this row.
    """
    __tablename__ = "learner_errors"

    learner_profile_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learner_profiles.id", ondelete="CASCADE"), index=True
    )
    skill_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("skills.id"), nullable=True)

    error_type: Mapped[str] = mapped_column(String(32))  # grammar|vocabulary|spelling|fluency|pronunciation
    category: Mapped[str] = mapped_column(String(64), index=True)  # e.g. past_tense, articles, prepositions
    description: Mapped[str] = mapped_column(String(500))

    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    severity: Mapped[str] = mapped_column(String(16), default="medium")  # low|medium|high
    weakness_score: Mapped[float] = mapped_column(Float, default=0.5)  # 0..1, higher = weaker

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    trend: Mapped[str] = mapped_column(String(16), default="stable")  # improving|stable|worsening


class ErrorOccurrence(Base, UUIDPKMixin, TimestampMixin):
    """A single instance of a mistake, tied back to the message/attempt it happened in."""
    __tablename__ = "error_occurrences"

    learner_error_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learner_errors.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_sessions.id"), nullable=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True)

    incorrect_text: Mapped[str] = mapped_column(String(500))
    correct_text: Mapped[str] = mapped_column(String(500))
    explanation: Mapped[str] = mapped_column(String(1000))
    confidence: Mapped[float] = mapped_column(Float, default=0.9)
