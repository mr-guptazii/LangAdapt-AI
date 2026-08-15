import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPKMixin


class TeachingStrategy(Base, UUIDPKMixin, TimestampMixin):
    """Log of which teaching strategy was applied and how it performed, so the
    Teaching Strategy Agent can learn which strategies work for which learners."""
    __tablename__ = "teaching_strategies"

    learner_profile_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learner_profiles.id", ondelete="CASCADE"), index=True
    )
    strategy: Mapped[str] = mapped_column(String(32))  # direct_explanation|socratic|conversational|repetition|examples|...
    skill_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("skills.id"), nullable=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    outcome_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # filled in after the following attempt(s)


class AgentDecision(Base, UUIDPKMixin, TimestampMixin):
    """Structured, non-chain-of-thought record of an agent decision (section 121),
    powering the 'Why this lesson?' UI (section 32)."""
    __tablename__ = "agent_decisions"

    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_sessions.id"), nullable=True
    )
    agent_name: Mapped[str] = mapped_column(String(32))  # adaptation|teaching_strategy|recommendation|...
    decision: Mapped[str] = mapped_column(String(64))  # e.g. increase_difficulty
    reason_code: Mapped[str] = mapped_column(String(64))
    reason_summary: Mapped[str] = mapped_column(String(500))
    confidence: Mapped[float] = mapped_column(Float)
    recommended_action: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_skill_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("skills.id"), nullable=True)
    inputs_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)  # the metrics that drove the decision
