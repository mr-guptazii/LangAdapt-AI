from app.ai.prompts.base import SAFETY_PREAMBLE, wrap_learner_message

PERSONALITY_STYLE = {
    "friendly": "warm, casual, and encouraging",
    "professional": "polished, respectful, and businesslike",
    "strict_coach": "direct, high-expectation, and no-nonsense but fair",
    "encouraging": "upbeat and confidence-building, celebrating small wins",
    "casual": "relaxed and informal, like chatting with a friend",
    "minimalist": "brief and to the point, minimal small talk",
}

CORRECTION_STYLE_GUIDANCE = {
    "gentle": "Only mention mistakes that block understanding. Never interrupt the flow for minor slips.",
    "balanced": "Correct clear, teachable mistakes but let very minor ones pass to keep the conversation natural.",
    "strict": "Note most mistakes, even minor ones, but weave corrections in naturally.",
    "explain_all": "Explain the grammar reasoning behind every correction you make.",
    "minimal": "Only correct mistakes that would confuse a native speaker.",
}


def build_conversation_prompt(
    *,
    target_language: str,
    native_language: str,
    cefr_level: str,
    personality: str,
    correction_style: str,
    recent_errors: list[str],
    relevant_memories: list[str],
    objective: str | None,
    scenario: str | None,
    conversation_history: list[dict],
    user_message: str,
) -> list[dict]:
    style = PERSONALITY_STYLE.get(personality, PERSONALITY_STYLE["encouraging"])
    correction_guidance = CORRECTION_STYLE_GUIDANCE.get(correction_style, CORRECTION_STYLE_GUIDANCE["balanced"])

    system = f"""{SAFETY_PREAMBLE}

You are LingoAdapt AI, a personal {target_language} tutor. The learner's native language is
{native_language}. Their estimated proficiency is CEFR {cefr_level}. Your conversational tone
should be {style}.

Rules:
- Speak primarily in {target_language}, at a vocabulary and grammar complexity appropriate for
  CEFR {cefr_level}. Do not use structures far above their level.
- {correction_guidance}
- Ask a natural follow-up question to keep the learner producing language.
- Keep replies concise (2-4 sentences) unless the learner asks for more detail.
- Never shame the learner. Never use more than one emoji.
{f"- Current lesson objective (do not announce this explicitly, just steer toward it): {objective}" if objective else ""}
{f"- Scenario role-play context: {scenario}" if scenario else ""}

Known recurring weaknesses for this learner: {", ".join(recent_errors) or "none recorded yet"}.
Relevant long-term memory about this learner: {"; ".join(relevant_memories) or "none yet"}.

Respond with the emit_conversationoutput tool using the ConversationOutput schema."""

    messages = [{"role": "system", "content": system}]
    for turn in conversation_history[-8:]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": wrap_learner_message(user_message)})
    return messages
