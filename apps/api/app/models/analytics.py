import uuid

from sqlalchemy import JSON, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPKMixin


class AnalyticsEvent(Base, UUIDPKMixin, TimestampMixin):
    """Event-based learning analytics (section 85-86). One row per learning
    event (lesson_started, question_answered, error_detected, ...); `payload`
    carries event-specific structured detail. This is the backing data for
    engagement trends and the admin dashboard's activity metrics — never
    inferred after the fact from other tables."""
    __tablename__ = "analytics_events"

    user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("learning_sessions.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class AIUsageLog(Base, UUIDPKMixin, TimestampMixin):
    """Per-LLM-call token/cost tracking (sections 42, 57). Populated from
    TutorState['usage_log'] in persist_learning_event, plus other services that
    call an LLMProvider directly (practice/assessment/recommendation generation).
    Backs the admin AI-usage dashboard — never estimated after the fact."""
    __tablename__ = "ai_usage_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("learning_sessions.id", ondelete="SET NULL"), nullable=True)
    node: Mapped[str] = mapped_column(String(64))  # which agent node / service made the call
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    tier: Mapped[str] = mapped_column(String(16), default="fast")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
