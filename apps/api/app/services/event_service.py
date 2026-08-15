"""Event-based learning analytics (section 85-86). A single, deliberately
boring helper: emit() inserts one AnalyticsEvent row into the CURRENT
transaction (it does not commit) so it never adds a second round-trip or
blocks the request — the calling code's own db.commit() covers it. If this
ever needs to become truly async/queued (e.g. very high write volume), the
call sites don't change, only what emit() does internally.
"""
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import AnalyticsEvent

# Canonical event type names (section 85). Using constants (not free-form
# strings at call sites) keeps the event vocabulary closed and typo-proof.
LESSON_STARTED = "lesson_started"
LESSON_COMPLETED = "lesson_completed"
QUESTION_ANSWERED = "question_answered"
QUESTION_FAILED = "question_failed"
ERROR_DETECTED = "error_detected"
SKILL_MASTERY_UPDATED = "skill_mastery_updated"
VOCABULARY_LEARNED = "vocabulary_learned"
VOCABULARY_REVIEWED = "vocabulary_reviewed"
CONVERSATION_STARTED = "conversation_started"
CONVERSATION_COMPLETED = "conversation_completed"
VOICE_SESSION_STARTED = "voice_session_started"
PRONUNCIATION_EVALUATED = "pronunciation_evaluated"
RECOMMENDATION_GENERATED = "recommendation_generated"
ASSESSMENT_STARTED = "assessment_started"
ASSESSMENT_COMPLETED = "assessment_completed"


def emit(
    db: AsyncSession, *, event_type: str, user_id: UUID | None,
    session_id: UUID | None = None, payload: dict[str, Any] | None = None,
) -> None:
    db.add(AnalyticsEvent(user_id=user_id, session_id=session_id, event_type=event_type, payload=payload or {}))
