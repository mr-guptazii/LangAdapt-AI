import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPKMixin


class LearningRecommendation(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "learning_recommendations"

    learner_profile_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learner_profiles.id", ondelete="CASCADE"), index=True
    )
    activity_type: Mapped[str] = mapped_column(String(24))  # conversation|grammar|vocabulary|speaking|listening|reading|writing
    title: Mapped[str] = mapped_column(String(200))
    reason_code: Mapped[str] = mapped_column(String(64))  # e.g. weak_skill, due_review, recent_mistake, goal_alignment
    reason_summary: Mapped[str] = mapped_column(String(500))
    target_skill_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("skills.id"), nullable=True)
    priority_score: Mapped[float] = mapped_column(Float)  # ranking score combining weakness/urgency/goal/variety
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=5)

    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|accepted|dismissed|completed
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
