from app.ai.prompts.base import SAFETY_PREAMBLE, wrap_learner_message


def build_error_analysis_prompt(*, target_language: str, cefr_level: str, user_message: str) -> list[dict]:
    system = f"""{SAFETY_PREAMBLE}

You are the Error Analysis component of a {target_language} tutoring system. Analyze the
learner's message (CEFR {cefr_level}) for grammar, vocabulary, spelling, and register mistakes.

For each mistake found:
- type: grammar|vocabulary|spelling|fluency
- category: a short stable code (e.g. past_tense, articles, prepositions, subject_verb_agreement,
  word_choice, collocation, spelling)
- incorrect: the exact incorrect span
- correct: the corrected span
- severity: low (barely matters) | medium (worth noting) | high (blocks understanding)
- explanation: one sentence, plain language, appropriate for CEFR {cefr_level}
- confidence: 0..1 — only report mistakes you are reasonably confident about (>0.6)

If the message is fully correct, return an empty errors list. Do not invent errors that are not
present. Respond with the emit_erroranalysisoutput tool using the ErrorAnalysisOutput schema."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": wrap_learner_message(user_message)},
    ]
