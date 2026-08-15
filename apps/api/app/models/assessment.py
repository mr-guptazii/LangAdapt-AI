import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPKMixin


class AssessmentSession(Base, UUIDPKMixin, TimestampMixin):
    """An adaptive CEFR placement test run (section 13)."""
    __tablename__ = "assessment_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="in_progress")  # in_progress|completed|abandoned
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    current_ability_estimate: Mapped[float] = mapped_column(Float, default=0.4)  # 0..1, updated each answer (IRT-lite)
    current_difficulty: Mapped[str] = mapped_column(String(4), default="A2")

    result_cefr_level: Mapped[str | None] = mapped_column(String(4), nullable=True)
    result_confidence_interval: Mapped[float | None] = mapped_column(Float, nullable=True)
    result_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)  # per-skill scores
    result_strengths: Mapped[list[str]] = mapped_column(JSON, default=list)
    result_weaknesses: Mapped[list[str]] = mapped_column(JSON, default=list)


class AssessmentQuestion(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "assessment_questions"

    assessment_session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessment_sessions.id", ondelete="CASCADE"), index=True
    )
    order_index: Mapped[int] = mapped_column(Integer)
    skill_area: Mapped[str] = mapped_column(String(24))  # vocabulary|grammar|reading|listening|writing|speaking
    difficulty: Mapped[str] = mapped_column(String(4))
    prompt: Mapped[str] = mapped_column(String(1000))
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    correct_answer: Mapped[str] = mapped_column(String(1000))


class AssessmentAnswer(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "assessment_answers"

    assessment_question_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessment_questions.id", ondelete="CASCADE"), index=True
    )
    user_answer: Mapped[str] = mapped_column(String(1000))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    ability_estimate_after: Mapped[float] = mapped_column(Float)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
