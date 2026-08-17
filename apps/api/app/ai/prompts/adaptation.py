from app.ai.prompts.base import SAFETY_PREAMBLE


def build_adaptation_prompt(*, metrics: dict) -> list[dict]:
    """metrics is a trusted, server-computed snapshot (accuracy, streak, mastery, etc.) —
    never learner-authored text — so no injection wrapping is needed here."""
    system = f"""{SAFETY_PREAMBLE}

You are the Difficulty Adaptation component. Given the learner's recent performance metrics,
decide whether to increase, maintain, or decrease difficulty.

Guidance (a floor, not a hard rule — weigh all signals together, including confidence,
engagement, and streak, not just raw accuracy):
- Recent accuracy >= 90% sustained -> lean toward increase_difficulty
- Recent accuracy 70-89% -> lean toward maintain
- Recent accuracy < 60% -> lean toward decrease_difficulty with reinforcement

Metrics snapshot:
{metrics}

Respond with the emit_adaptationdecision tool using the AdaptationDecision schema. reason_code
must be a short stable machine code (e.g. high_recent_accuracy, repeated_mistakes, low_engagement).
recommended_action is shown as a single line in a "Why this lesson?" UI card — one concise
sentence, under 150 characters. Not a paragraph, not a numbered list of suggestions."""
    return [{"role": "system", "content": system}, {"role": "user", "content": "Decide."}]
