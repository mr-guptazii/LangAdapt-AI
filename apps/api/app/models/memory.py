import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.database.base import Base, TimestampMixin, UUIDPKMixin


class LearnerMemory(Base, UUIDPKMixin, TimestampMixin):
    """A structured, human-readable long-term memory fact (section 120) — e.g.
    'User frequently confuses present perfect and simple past.' NOT raw chat log.
    """
    __tablename__ = "learner_memories"

    learner_profile_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learner_profiles.id", ondelete="CASCADE"), index=True
    )
    memory_type: Mapped[str] = mapped_column(String(32))  # recurring_mistake|mastered_topic|preference|milestone|strategy_success
    content: Mapped[str] = mapped_column(String(1000))
    importance: Mapped[float] = mapped_column(Float, default=0.5)  # 0..1, decays retrieval priority over time
    related_skill_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("skills.id"), nullable=True)
    source_session_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_sessions.id"), nullable=True
    )
    last_reinforced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SemanticMemory(Base, UUIDPKMixin, TimestampMixin):
    """Embedding-indexed memory for semantic retrieval via pgvector. Populated
    alongside LearnerMemory rows so relevant memories can be retrieved by meaning,
    not just by type/recency filters."""
    __tablename__ = "semantic_memories"

    learner_profile_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learner_profiles.id", ondelete="CASCADE"), index=True
    )
    learner_memory_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learner_memories.id", ondelete="CASCADE"), nullable=True
    )
    text: Mapped[str] = mapped_column(String(1000))
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.EMBEDDING_DIM))
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
