"""learner_model_agent, adaptation_agent, teaching_strategy_agent (sections 8, 10, 11).

Only invoked when the router decided this turn is a "significant learning event"
(see agents/graph.py) — this is the cost-optimization routing from section 42.
"""
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import TutorState
from app.ai.prompts.adaptation import build_adaptation_prompt
from app.ai.prompts.teaching_strategy import build_teaching_strategy_prompt
from app.ai.providers.base import LLMMessage, ModelTier
from app.ai.providers.factory import get_llm_provider
from app.core.logging import get_logger
from app.learning.mastery import update_mastery
from app.schemas.agent_io import AdaptationDecision, TeachingStrategyDecision
from app.tools import learner_tools

logger = get_logger(__name__)


async def learner_model_agent(state: TutorState, db: AsyncSession) -> dict:
    """Updates skill_mastery for each detected error's category, in-memory (DB
    persistence happens in persist_learning_event so a failed downstream node
    can't leave a half-applied write)."""
    profile_id = UUID(state["learner_profile_id"])
    profile = await learner_tools.get_learner_profile(db, profile_id)
    target_lang = profile.target_language_code if profile else "en"

    skill_updates = []
    for err in state.get("detected_errors", []):
        skill = await learner_tools.get_skill_by_code(db, target_lang, err["category"])
        if skill is None:
            continue
        mastery_row = await learner_tools.get_or_create_skill_mastery(db, profile_id, skill.id)
        result = update_mastery(current_mastery=mastery_row.mastery, is_correct=False, difficulty=profile.cefr_level if profile else "A2")
        skill_updates.append({
            "skill_id": str(skill.id), "skill_code": skill.code, "skill_name": skill.name,
            "previous_mastery": mastery_row.mastery, "new_mastery": result.new_mastery, "delta": result.delta,
        })

    return {
        "skill_updates": skill_updates,
        "agents_invoked": state.get("agents_invoked", []) + ["learner_model_agent"],
    }


def _recent_accuracy_metrics(state: TutorState) -> dict:
    profile = state.get("learner_profile", {})
    return {
        "recent_message_had_errors": len(state.get("detected_errors", [])) > 0,
        "error_count_this_turn": len(state.get("detected_errors", [])),
        "grammar_ability": profile.get("grammar_ability", 0.5),
        "confidence_score": profile.get("confidence_score", 0.5),
        "engagement_score": profile.get("engagement_score", 0.5),
        "current_difficulty": profile.get("current_difficulty", "A2"),
        "recurring_error_categories": state.get("recent_error_categories", []),
    }


async def adaptation_agent(state: TutorState) -> dict:
    provider = get_llm_provider()
    metrics = _recent_accuracy_metrics(state)
    messages = build_adaptation_prompt(metrics=metrics)
    llm_messages = [LLMMessage(role=m["role"], content=m["content"]) for m in messages]

    # Same graceful-degradation guard as conversation_agent/error_analysis_agent
    # (see app/agents/nodes/conversation.py) — this node previously had none,
    # which was a latent gap that only started surfacing as a hard 500 once a
    # flakier model was in place (observed live: an intermittent forced
    # tool-call failure here crashed the whole turn even on a trivial
    # message). "maintain" is the safe no-op default: skip this turn's
    # difficulty adjustment rather than lose the reply entirely.
    try:
        result, usage = await provider.structured(llm_messages, AdaptationDecision, tier=ModelTier.FAST, max_tokens=300)
    except Exception:
        logger.warning("adaptation_agent_failed_degrading_gracefully", exc_info=True)
        return {
            "difficulty_decision": {
                "decision": "maintain", "reason_code": "adaptation_agent_unavailable",
                "confidence": 0.0, "recommended_action": "No change this turn.",
                "target_skill": None, "inputs_snapshot": metrics,
            },
            "agents_invoked": state.get("agents_invoked", []) + ["adaptation_agent"],
        }

    usage_log = state.get("usage_log", [])
    usage_log.append({"node": "adaptation_agent", "provider": usage.provider, "model": usage.model,
                       "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens})

    decision = result.model_dump()
    decision["inputs_snapshot"] = metrics
    return {
        "difficulty_decision": decision,
        "usage_log": usage_log,
        "agents_invoked": state.get("agents_invoked", []) + ["adaptation_agent"],
    }


async def teaching_strategy_agent(state: TutorState) -> dict:
    provider = get_llm_provider()
    # "recent_errors" is history loaded BEFORE this turn (context.py runs first
    # in the graph); it never includes what error_analysis_agent just detected
    # THIS turn, which is exactly the signal that routed the graph into this
    # significant-learning-event branch in the first place — without it the
    # strategy decision was blind to the very error that triggered it.
    learner_summary = {
        **state.get("learner_profile", {}),
        "preferences": state.get("learning_preferences", {}),
        "recent_errors": state.get("recent_error_categories", []),
        "current_turn_errors": [e["category"] for e in state.get("detected_errors", [])],
    }
    difficulty_decision = state.get("difficulty_decision", {}).get("decision", "maintain")
    messages = build_teaching_strategy_prompt(learner_summary=learner_summary, difficulty_decision=difficulty_decision)
    llm_messages = [LLMMessage(role=m["role"], content=m["content"]) for m in messages]

    # Same graceful-degradation guard as adaptation_agent above — "conversational"
    # is the same safe default persist_learning_event/generate_response already
    # fall back to elsewhere (see app/agents/nodes/persistence.py) when no
    # explicit strategy is set.
    try:
        result, usage = await provider.structured(llm_messages, TeachingStrategyDecision, tier=ModelTier.FAST, max_tokens=300)
    except Exception:
        logger.warning("teaching_strategy_agent_failed_degrading_gracefully", exc_info=True)
        return {
            "teaching_strategy": {
                "strategy": "conversational", "reason_code": "teaching_strategy_agent_unavailable",
                "reason_summary": "Defaulted after the strategy model was unavailable this turn.", "confidence": 0.0,
            },
            "agents_invoked": state.get("agents_invoked", []) + ["teaching_strategy_agent"],
        }

    usage_log = state.get("usage_log", [])
    usage_log.append({"node": "teaching_strategy_agent", "provider": usage.provider, "model": usage.model,
                       "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens})

    return {
        "teaching_strategy": result.model_dump(),
        "usage_log": usage_log,
        "agents_invoked": state.get("agents_invoked", []) + ["teaching_strategy_agent"],
    }
