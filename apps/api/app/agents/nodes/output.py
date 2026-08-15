"""practice_or_response_agent + generate_response (final leg of the graph)."""
from app.agents.state import TutorState


async def practice_or_response_agent(state: TutorState) -> dict:
    """Decides whether this turn should surface a lightweight practice nudge
    alongside the conversational response. Kept deterministic (not another LLM
    call) — it just reads the upstream agents' structured decisions."""
    strategy = state.get("teaching_strategy", {}).get("strategy")
    recommend_practice = strategy in ("guided_practice", "multiple_choice", "repetition") and bool(state.get("detected_errors"))

    recommended_activity = None
    if recommend_practice and state.get("detected_errors"):
        top_error = state["detected_errors"][0]
        recommended_activity = {
            "activity_type": "grammar",
            "reason": f"You just made a {top_error['category']} mistake — a quick targeted drill will help it stick.",
            "target_skill_code": top_error["category"],
        }

    return {
        "recommended_activity": recommended_activity,
        "agents_invoked": state.get("agents_invoked", []) + ["practice_or_response_agent"],
    }


async def generate_response(state: TutorState) -> dict:
    """Assembles the final API-facing response from the conversation agent's
    output plus any correction cards derived from detected errors."""
    conv = state.get("conversation_output", {})
    return {
        "response": conv.get("response", ""),
        "follow_up_question": conv.get("follow_up_question", ""),
        "agents_invoked": state.get("agents_invoked", []) + ["generate_response"],
    }
