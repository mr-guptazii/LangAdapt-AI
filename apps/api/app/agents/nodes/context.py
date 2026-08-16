"""load_learner_context + retrieve_relevant_memory nodes (section 41, steps 1-2)."""
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import TutorState
from app.memory.service import retrieve_relevant_memories
from app.tools import learner_tools


async def load_learner_context(state: TutorState, db: AsyncSession) -> dict:
    profile_id = UUID(state["learner_profile_id"])
    profile = await learner_tools.get_learner_profile(db, profile_id)
    prefs = await learner_tools.get_learning_preferences(db, profile_id)
    recent_errors = await learner_tools.get_recent_errors(db, profile_id, limit=5)
    account = await learner_tools.get_profile_settings(db, UUID(state["user_id"]))

    # personalization_enabled is a real privacy opt-out (section 72): when off,
    # traits fall back to defaults instead of being loaded into agent state at
    # all, so a disabled learner's actual personality/interests never reach an
    # LLM prompt even indirectly.
    personalize = account.personalization_enabled if account else True

    profile_dict = {
        "cefr_level": profile.cefr_level,
        "target_language": profile.target_language_code,
        "native_language": profile.native_language_code,
        "grammar_ability": profile.grammar_ability,
        "vocabulary_ability": profile.vocabulary_ability,
        "speaking_ability": profile.speaking_ability,
        "confidence_score": profile.confidence_score,
        "engagement_score": profile.engagement_score,
        "current_difficulty": profile.current_difficulty,
        "ai_personality": (account.ai_personality if (account and personalize) else "encouraging"),
        "interests": (account.interests if (account and personalize) else []),
    } if profile else {}

    prefs_dict = {
        "correction_style": prefs.correction_style,
        "preferred_explanation_length": prefs.preferred_explanation_length,
        "challenge_tolerance": prefs.challenge_tolerance,
        "conversation_affinity": prefs.conversation_affinity,
    } if prefs else {}

    return {
        "learner_profile": profile_dict,
        "learning_preferences": prefs_dict,
        "recent_error_categories": [e.category for e in recent_errors],
        "agents_invoked": ["load_learner_context"],
    }


async def retrieve_relevant_memory(state: TutorState, db: AsyncSession) -> dict:
    profile_id = UUID(state["learner_profile_id"])
    memories = await retrieve_relevant_memories(
        db, learner_profile_id=profile_id, query_text=state["user_message"], top_k=5
    )
    return {
        "relevant_memories": memories,
        "agents_invoked": state.get("agents_invoked", []) + ["retrieve_relevant_memory"],
    }
