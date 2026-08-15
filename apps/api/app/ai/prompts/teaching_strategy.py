from app.ai.prompts.base import SAFETY_PREAMBLE


def build_teaching_strategy_prompt(*, learner_summary: dict, difficulty_decision: str) -> list[dict]:
    system = f"""{SAFETY_PREAMBLE}

You are the Teaching Strategy component. Choose HOW to teach this learner right now, given
their profile and the current difficulty decision ({difficulty_decision}).

Available strategies: direct_explanation, socratic, conversational, repetition, examples,
analogy, multiple_choice, guided_practice, free_response, correction_first, delayed_correction,
challenge_mode, confidence_building.

General guidance:
- Repeated failure on a skill -> direct_explanation or examples, then guided_practice
- Strong recent performance -> reduce explanation, prefer free_response or challenge_mode
- Low confidence_score even with decent ability -> confidence_building, delayed_correction
- High confidence_score with low ability -> correction_first, guided_practice

Learner summary:
{learner_summary}

Respond with the emit_teachingstrategydecision tool using the TeachingStrategyDecision schema."""
    return [{"role": "system", "content": system}, {"role": "user", "content": "Decide."}]
