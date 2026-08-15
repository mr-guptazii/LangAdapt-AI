import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPKMixin


class SkillMastery(Base, UUIDPKMixin, TimestampMixin):
    """Per-learner, per-skill mastery score plus spaced-repetition scheduling fields.

    mastery is a 0..1 estimate maintained by app.learning.mastery.update_mastery().
    The SRS fields (ease/interval/repetitions/next_review_at) follow a simplified
    SM-2-style scheduler — see app.learning.spaced_repetition for the documented
    simplification vs. full FSRS.
    """
    __tablename__ = "skill_mastery"

    learner_profile_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learner_profiles.id", ondelete="CASCADE"), index=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("skills.id"), index=True)

    mastery: Mapped[float] = mapped_column(Float, default=0.0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct_attempts: Mapped[int] = mapped_column(Integer, default=0)

    # spaced repetition scheduling
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[float] = mapped_column(Float, default=0.0)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    retention_estimate: Mapped[float] = mapped_column(Float, default=1.0)

    __table_args__ = ()
