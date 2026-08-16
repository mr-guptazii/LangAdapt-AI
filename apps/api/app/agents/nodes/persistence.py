"""persist_learning_event, update_memory, update_recommendations (final section 41 steps).

All DB writes for a turn happen here, in one place, after every upstream agent
has succeeded — so a failure mid-graph never leaves a half-applied mutation.
"""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import TutorState
from app.learning.curriculum import next_cefr_level, previous_cefr_level
from app.memory.service import store_memory
from app.models.agent import AgentDecision
from app.models.analytics import AIUsageLog
from app.models.errors import ErrorOccurrence, LearnerError
from app.services import event_service
from app.services.usage_cost import estimate_cost_usd
from app.tools import learner_tools


async def persist_learning_event(state: TutorState, db: AsyncSession) -> dict:
    profile_id = UUID(state["learner_profile_id"])
    user_id = UUID(state["user_id"])
    session_id = UUID(state["session_id"]) if state.get("session_id") else None
    now = datetime.now(timezone.utc)

    # Roll detected errors up into LearnerError aggregates (section 15/16).
    for err in state.get("detected_errors", []):
        result = await db.execute(
            select(LearnerError).where(
                LearnerError.learner_profile_id == profile_id, LearnerError.category == err["category"]
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.occurrence_count += 1
            existing.last_seen_at = now
            existing.weakness_score = min(1.0, existing.weakness_score + 0.05)
            existing.trend = "worsening" if existing.occurrence_count % 3 == 0 else existing.trend
            learner_error = existing
        else:
            learner_error = LearnerError(
                learner_profile_id=profile_id, error_type=err["type"], category=err["category"],
                description=err["explanation"], occurrence_count=1, severity=err["severity"],
                weakness_score=0.5, first_seen_at=now, last_seen_at=now, trend="stable",
            )
            db.add(learner_error)
            await db.flush()

        db.add(ErrorOccurrence(
            learner_error_id=learner_error.id, session_id=session_id,
            incorrect_text=err["incorrect"], correct_text=err["correct"],
            explanation=err["explanation"], confidence=err["confidence"],
        ))
        event_service.emit(
            db, event_type=event_service.ERROR_DETECTED, user_id=user_id, session_id=session_id,
            payload={"category": err["category"], "type": err["type"], "severity": err["severity"]},
        )

    # Persist mastery deltas computed by learner_model_agent.
    for update in state.get("skill_updates", []):
        mastery_row = await learner_tools.get_or_create_skill_mastery(db, profile_id, UUID(update["skill_id"]))
        mastery_row.mastery = update["new_mastery"]
        mastery_row.attempts += 1
        event_service.emit(
            db, event_type=event_service.SKILL_MASTERY_UPDATED, user_id=user_id, session_id=session_id,
            payload={"skill_code": update["skill_code"], "new_mastery": update["new_mastery"], "delta": update["delta"]},
        )

    # AI usage tracking (sections 42, 57) — one row per LLM call this turn.
    for entry in state.get("usage_log", []):
        tier = "strong" if entry.get("node") == "conversation_agent" else "fast"
        db.add(AIUsageLog(
            user_id=user_id, session_id=session_id, node=entry.get("node", "unknown"),
            provider=entry.get("provider", ""), model=entry.get("model", ""), tier=tier,
            input_tokens=entry.get("input_tokens", 0), output_tokens=entry.get("output_tokens", 0),
            estimated_cost_usd=estimate_cost_usd(entry.get("model", ""), entry.get("input_tokens", 0), entry.get("output_tokens", 0)),
        ))

    # Log the adaptation decision for the "Why this lesson?" UI (section 32/121)
    # AND actually apply it — previously this decision was computed, logged, and
    # returned to the client, but never fed back into LearnerProfile.current_difficulty,
    # so it could never change what CEFR level future turns were pitched at. A real
    # decision that isn't applied isn't adaptation, just a label.
    if state.get("difficulty_decision"):
        d = state["difficulty_decision"]
        decision = d.get("decision", "maintain")
        db.add(AgentDecision(
            user_id=user_id, session_id=session_id, agent_name="adaptation", decision=decision,
            reason_code=d.get("reason_code", "unspecified"), reason_summary=d.get("recommended_action", ""),
            confidence=d.get("confidence", 0.5), recommended_action=d.get("recommended_action"),
            inputs_snapshot=d.get("inputs_snapshot", {}),
        ))
        if decision in ("increase_difficulty", "decrease_difficulty"):
            profile = await learner_tools.get_learner_profile(db, profile_id)
            if profile:
                profile.current_difficulty = (
                    next_cefr_level(profile.current_difficulty) if decision == "increase_difficulty"
                    else previous_cefr_level(profile.current_difficulty)
                )
    if state.get("teaching_strategy"):
        t = state["teaching_strategy"]
        db.add(AgentDecision(
            user_id=user_id, session_id=session_id, agent_name="teaching_strategy", decision=t.get("strategy", "conversational"),
            reason_code=t.get("reason_code", "unspecified"), reason_summary=t.get("reason_summary", ""),
            confidence=t.get("confidence", 0.5), recommended_action=t.get("strategy"), inputs_snapshot={},
        ))

    await db.flush()
    return {"agents_invoked": state.get("agents_invoked", []) + ["persist_learning_event"]}


async def update_memory_node(state: TutorState, db: AsyncSession) -> dict:
    """Writes structured long-term memory facts, NOT raw chat (section 120)."""
    profile_id = UUID(state["learner_profile_id"])
    errors = state.get("detected_errors", [])
    if not errors:
        return {"agents_invoked": state.get("agents_invoked", []) + ["update_memory"]}

    for err in errors:
        recurrence = next((c for c in state.get("recent_error_categories", []) if c == err["category"]), None)
        if recurrence:
            await store_memory(
                db, learner_profile_id=profile_id, memory_type="recurring_mistake",
                content=f"User repeatedly struggles with {err['category']} (e.g. '{err['incorrect']}' instead of '{err['correct']}').",
                importance=0.8,
            )
    return {"agents_invoked": state.get("agents_invoked", []) + ["update_memory"]}


async def update_recommendations_node(state: TutorState, db: AsyncSession) -> dict:
    """Lightweight per-turn signal only; the full ranked recommendation list is
    (re)computed by app.services.recommendation_service on dashboard load, since
    that needs a fuller picture (due reviews, goals, fatigue) than one turn has."""
    return {"agents_invoked": state.get("agents_invoked", []) + ["update_recommendations"]}
