"""Orchestrates one conversational turn: loads/creates the session, runs the
LangGraph tutor graph, and shapes the result into the API response contract.
This is the module app/api/v1/chat.py delegates to."""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import run_tutor_turn
from app.agents.state import TutorState
from app.models.learner import LearnerProfile
from app.models.session import LearningSession, Message
from app.schemas.api import CorrectionCard, SendMessageRequest, SendMessageResponse
from app.services import event_service


async def _get_or_create_session(
    db: AsyncSession, *, user_id: UUID, learner_profile: LearnerProfile, req: SendMessageRequest
) -> tuple[LearningSession, bool]:
    if req.session_id:
        result = await db.execute(select(LearningSession).where(LearningSession.id == req.session_id, LearningSession.user_id == user_id))
        session = result.scalar_one_or_none()
        if session:
            return session, False
    session = LearningSession(user_id=user_id, mode=req.mode, started_at=datetime.now(timezone.utc), difficulty=learner_profile.current_difficulty)
    db.add(session)
    await db.flush()
    return session, True


async def _recent_history(db: AsyncSession, session_id: UUID, limit: int = 10) -> list[dict]:
    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at.desc()).limit(limit)
    )
    rows = list(reversed(result.scalars().all()))
    return [{"role": m.role, "content": m.content} for m in rows]


async def send_message(db: AsyncSession, *, user_id: UUID, learner_profile: LearnerProfile, req: SendMessageRequest) -> SendMessageResponse:
    session, is_new_session = await _get_or_create_session(db, user_id=user_id, learner_profile=learner_profile, req=req)
    if is_new_session:
        event_service.emit(db, event_type=event_service.CONVERSATION_STARTED, user_id=user_id, session_id=session.id, payload={"mode": req.mode})
    history = await _recent_history(db, session.id)

    user_msg = Message(session_id=session.id, role="user", content=req.message, input_mode=req.input_mode)
    db.add(user_msg)
    await db.flush()

    initial_state: TutorState = {
        "user_id": str(user_id),
        "session_id": str(session.id),
        "learner_profile_id": str(learner_profile.id),
        "input_mode": req.input_mode,
        "user_message": req.message,
        "conversation_context": history,
        "usage_log": [],
        "agents_invoked": [],
    }
    result = await run_tutor_turn(db, initial_state)

    conv_out = result.get("conversation_output", {})
    assistant_msg = Message(
        session_id=session.id, role="assistant", content=result.get("response", ""),
        correction_needed=conv_out.get("correction_needed"), correction_priority=conv_out.get("correction_priority"),
        teaching_intent=conv_out.get("teaching_intent"),
    )
    db.add(assistant_msg)
    await db.commit()

    corrections = [
        CorrectionCard(type=e["type"], category=e["category"], incorrect=e["incorrect"], correct=e["correct"],
                        severity=e["severity"], explanation=e["explanation"])
        for e in result.get("detected_errors", [])
    ]

    # Never silently present a mock-generated reply as real (section 98) — this
    # was previously the one surface with zero indication: voice endpoints
    # already set is_mock, chat did not. usage_log entries carry the real
    # provider name from whichever LLMProvider actually ran this turn.
    is_mock = any(entry.get("provider") == "mock" for entry in result.get("usage_log", []))

    return SendMessageResponse(
        session_id=session.id,
        response=result.get("response", ""),
        follow_up_question=result.get("follow_up_question", ""),
        corrections=corrections,
        teaching_strategy=result.get("teaching_strategy", {}).get("strategy"),
        difficulty_decision=result.get("difficulty_decision", {}).get("decision"),
        recommended_activity=result.get("recommended_activity"),
        agents_invoked=result.get("agents_invoked", []),
        is_mock=is_mock,
    )
