"""conversation_agent + error_analysis_agent nodes (sections 6-7)."""
from app.agents.state import TutorState
from app.ai.prompts.conversation import build_conversation_prompt
from app.ai.prompts.error_analysis import build_error_analysis_prompt
from app.ai.providers.base import LLMMessage, ModelTier
from app.ai.providers.factory import get_llm_provider
from app.schemas.agent_io import ConversationOutput, ErrorAnalysisOutput


async def conversation_agent(state: TutorState) -> dict:
    provider = get_llm_provider()
    profile = state.get("learner_profile", {})
    prefs = state.get("learning_preferences", {})

    messages = build_conversation_prompt(
        target_language=profile.get("target_language", "the target language"),
        native_language=profile.get("native_language", "the learner's native language"),
        cefr_level=profile.get("cefr_level", "A2"),
        personality=profile.get("ai_personality", "encouraging"),
        correction_style=prefs.get("correction_style", "balanced"),
        explanation_length=prefs.get("preferred_explanation_length", "medium"),
        interests=profile.get("interests", []),
        recent_errors=state.get("recent_error_categories", []),
        relevant_memories=state.get("relevant_memories", []),
        objective=None,
        scenario=None,
        conversation_history=state.get("conversation_context", []),
        user_message=state["user_message"],
    )
    llm_messages = [LLMMessage(role=m["role"], content=m["content"]) for m in messages]
    result, usage = await provider.structured(llm_messages, ConversationOutput, tier=ModelTier.STRONG, max_tokens=600)

    usage_log = state.get("usage_log", [])
    usage_log.append({"node": "conversation_agent", "provider": usage.provider, "model": usage.model,
                       "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens})

    return {
        "conversation_output": result.model_dump(),
        "usage_log": usage_log,
        "agents_invoked": state.get("agents_invoked", []) + ["conversation_agent"],
    }


async def error_analysis_agent(state: TutorState) -> dict:
    provider = get_llm_provider()
    profile = state.get("learner_profile", {})
    messages = build_error_analysis_prompt(
        target_language=profile.get("target_language", "the target language"),
        cefr_level=profile.get("cefr_level", "A2"),
        user_message=state["user_message"],
    )
    llm_messages = [LLMMessage(role=m["role"], content=m["content"]) for m in messages]
    result, usage = await provider.structured(llm_messages, ErrorAnalysisOutput, tier=ModelTier.FAST, max_tokens=500)

    usage_log = state.get("usage_log", [])
    usage_log.append({"node": "error_analysis_agent", "provider": usage.provider, "model": usage.model,
                       "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens})

    errors = [e.model_dump() for e in result.errors]
    return {
        "detected_errors": errors,
        "is_significant_learning_event": len(errors) > 0,
        "usage_log": usage_log,
        "agents_invoked": state.get("agents_invoked", []) + ["error_analysis_agent"],
    }
