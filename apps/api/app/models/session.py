import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPKMixin


class LearningSession(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "learning_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(24))  # conversation|grammar|vocabulary|speaking|listening|reading|writing|assessment
    scenario: Mapped[str | None] = mapped_column(String(64), nullable=True)
    objective: Mapped[str | None] = mapped_column(String(128), nullable=True)  # e.g. "past_tense_practice"
    difficulty: Mapped[str] = mapped_column(String(16), default="A2")

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)

    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Message(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user|assistant|system
    content: Mapped[str] = mapped_column(String(4000))
    input_mode: Mapped[str] = mapped_column(String(16), default="text")  # text|voice

    # Conversation-agent structured output (section 6), null for user messages
    correction_needed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    correction_priority: Mapped[str | None] = mapped_column(String(16), nullable=True)
    teaching_intent: Mapped[str | None] = mapped_column(String(64), nullable=True)

    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class ConversationTurn(Base, UUIDPKMixin, TimestampMixin):
    """Aggregated view of one user-turn -> assistant-turn exchange, with the full
    agent decision trail attached for the 'why this lesson' feature (section 32)."""
    __tablename__ = "conversation_turns"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_sessions.id", ondelete="CASCADE"), index=True
    )
    user_message_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("messages.id"))
    assistant_message_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("messages.id"))

    detected_errors: Mapped[list] = mapped_column(JSON, default=list)
    difficulty_decision: Mapped[dict] = mapped_column(JSON, default=dict)
    teaching_strategy: Mapped[dict] = mapped_column(JSON, default=dict)
    agents_invoked: Mapped[list[str]] = mapped_column(JSON, default=list)  # which nodes ran (routing trace)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
