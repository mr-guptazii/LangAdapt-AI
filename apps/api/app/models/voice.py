import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPKMixin


class VoiceSession(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "voice_sessions"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_sessions.id", ondelete="CASCADE"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stt_provider: Mapped[str] = mapped_column(String(32))
    tts_provider: Mapped[str] = mapped_column(String(32))
    raw_audio_retained: Mapped[bool] = mapped_column(Boolean, default=False)  # section 72: default false


class SpeechAnalysis(Base, UUIDPKMixin, TimestampMixin):
    """Per-utterance speech analysis result. Speaking/pronunciation/fluency scores
    are kept as SEPARATE fields from raw STT confidence, per section 20 — never
    conflate ASR confidence with pronunciation quality."""
    __tablename__ = "speech_analysis"

    voice_session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("voice_sessions.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True)

    transcript: Mapped[str] = mapped_column(String(2000))
    asr_confidence: Mapped[float] = mapped_column(Float)  # raw STT engine confidence, NOT pronunciation quality

    speaking_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    fluency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    speaking_rate_wpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    pause_count: Mapped[int] = mapped_column(Integer, default=0)
    filler_word_count: Mapped[int] = mapped_column(Integer, default=0)
    repeated_word_count: Mapped[int] = mapped_column(Integer, default=0)


class PronunciationScore(Base, UUIDPKMixin, TimestampMixin):
    """Kept as its own table (not folded into SpeechAnalysis) so that when a real
    phoneme-level provider is plugged in, its richer output has a dedicated home."""
    __tablename__ = "pronunciation_scores"

    speech_analysis_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("speech_analysis.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32))
    overall_score: Mapped[float] = mapped_column(Float)
    is_estimated: Mapped[bool] = mapped_column(Boolean, default=True)  # True while only mock/heuristic provider is configured
    phoneme_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # populated only by phoneme-capable providers
