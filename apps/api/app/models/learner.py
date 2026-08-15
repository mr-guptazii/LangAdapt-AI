import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.user import User


class LearnerProfile(Base, UUIDPKMixin, TimestampMixin):
    """The evolving model of a learner: proficiency, ability estimates, and engagement stats.

    This is read by nearly every agent node — it is the closest thing the system has
    to "who is this learner and how are they doing right now".
    """
    __tablename__ = "learner_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    native_language_code: Mapped[str] = mapped_column(String(8), default="en")
    target_language_code: Mapped[str] = mapped_column(String(8), default="es")

    cefr_level: Mapped[str] = mapped_column(String(4), default="A2")
    proficiency_confidence: Mapped[float] = mapped_column(Float, default=0.4)  # 0..1, how sure we are

    # Skill-area ability estimates, 0..1
    grammar_ability: Mapped[float] = mapped_column(Float, default=0.3)
    vocabulary_ability: Mapped[float] = mapped_column(Float, default=0.3)
    speaking_ability: Mapped[float] = mapped_column(Float, default=0.3)
    listening_ability: Mapped[float] = mapped_column(Float, default=0.3)
    reading_ability: Mapped[float] = mapped_column(Float, default=0.3)
    writing_ability: Mapped[float] = mapped_column(Float, default=0.3)
    pronunciation_ability: Mapped[float] = mapped_column(Float, default=0.3)
    fluency_ability: Mapped[float] = mapped_column(Float, default=0.3)

    # Learner-state metrics used by the adaptation agent
    confidence_score: Mapped[float] = mapped_column(Float, default=0.5)  # self-belief, distinct from ability
    consistency_score: Mapped[float] = mapped_column(Float, default=0.5)
    engagement_score: Mapped[float] = mapped_column(Float, default=0.5)
    learning_speed: Mapped[float] = mapped_column(Float, default=0.5)  # how fast mastery tends to rise

    current_difficulty: Mapped[str] = mapped_column(String(16), default="A2")
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    total_study_minutes: Mapped[int] = mapped_column(Integer, default=0)
    last_active_at: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped["User"] = relationship(back_populates="learner_profile")
    goals: Mapped[list["LearningGoal"]] = relationship(back_populates="learner_profile", cascade="all, delete-orphan")
    preferences: Mapped["LearningPreference"] = relationship(
        back_populates="learner_profile", uselist=False, cascade="all, delete-orphan"
    )


class LearningGoal(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "learning_goals"

    learner_profile_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learner_profiles.id", ondelete="CASCADE")
    )
    goal_type: Mapped[str] = mapped_column(String(32))  # travel, academic, career, interview, daily_conversation, ...
    priority: Mapped[int] = mapped_column(Integer, default=1)

    learner_profile: Mapped["LearnerProfile"] = relationship(back_populates="goals")


class LearningPreference(Base, UUIDPKMixin, TimestampMixin):
    """Inferred (not just self-reported) personalization signals. Section 9.

    Values are 0..1 propensity scores that the personalization engine updates
    over time based on observed engagement, not only onboarding answers.
    """
    __tablename__ = "learning_preferences"

    learner_profile_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learner_profiles.id", ondelete="CASCADE"), unique=True
    )

    conversation_affinity: Mapped[float] = mapped_column(Float, default=0.5)
    quiz_affinity: Mapped[float] = mapped_column(Float, default=0.5)
    reading_affinity: Mapped[float] = mapped_column(Float, default=0.5)
    listening_affinity: Mapped[float] = mapped_column(Float, default=0.5)

    preferred_explanation_length: Mapped[str] = mapped_column(String(16), default="medium")  # short|medium|long
    example_preference: Mapped[float] = mapped_column(Float, default=0.6)
    repetition_preference: Mapped[float] = mapped_column(Float, default=0.5)
    challenge_tolerance: Mapped[float] = mapped_column(Float, default=0.5)
    correction_style: Mapped[str] = mapped_column(String(16), default="balanced")  # gentle|balanced|strict|explain_all|minimal
    preferred_pace: Mapped[str] = mapped_column(String(16), default="medium")  # slow|medium|fast

    interests: Mapped[list[str]] = mapped_column(JSON, default=list)
    preferred_topics: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Free-form evidence trail so the "why" is inspectable, e.g. {"quiz_affinity": ["completed 8/8 quizzes in a row"]}
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)

    learner_profile: Mapped["LearnerProfile"] = relationship(back_populates="preferences")
