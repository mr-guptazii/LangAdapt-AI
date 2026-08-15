import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPKMixin


class PracticeQuestion(Base, UUIDPKMixin, TimestampMixin):
    """A generated (or curated) exercise. Carries provenance back to the error/skill
    that caused it to be generated, per section 12."""
    __tablename__ = "practice_questions"

    skill_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("skills.id"), nullable=True)
    source_error_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learner_errors.id"), nullable=True
    )
    source_skill_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("skills.id"), nullable=True)
    for_learner_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learner_profiles.id"), nullable=True
    )  # null = generic/reusable question bank item

    question_type: Mapped[str] = mapped_column(String(32))  # multiple_choice|fill_blank|correction|transformation|ordering|contextual|free_response
    difficulty: Mapped[str] = mapped_column(String(4))  # CEFR level
    prompt: Mapped[str] = mapped_column(String(1000))
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    correct_answer: Mapped[str] = mapped_column(String(1000))
    explanation: Mapped[str] = mapped_column(String(1000))
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)  # anti-repetition dedup key (section 88)

    validated: Mapped[bool] = mapped_column(Boolean, default=False)


class PracticeAttempt(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "practice_attempts"

    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("practice_questions.id"))
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_sessions.id"), nullable=True
    )

    user_answer: Mapped[str] = mapped_column(String(1000))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    response_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
