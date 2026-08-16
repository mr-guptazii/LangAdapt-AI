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

Resolving tense ambiguity (this is where most real mistakes get missed): a time marker like
"today" or "this morning" combined with a bare present-tense verb ("today I go...", "today I
buy...") is a language learner recounting something that already happened — the single most
common real mistake this system exists to catch — NOT a future plan, unless the sentence has an
explicit future/plan marker ("tomorrow", "next week", "will", "going to", "planning to", "I'm
going to"). Default to the past-tense reading and flag it as a past_tense error; do not propose
present continuous ("I'm going") as the fix for a time-marker-plus-bare-verb sentence unless a
future marker is actually present.

Never propose changing a pronoun (I/we/he/she/they) unless the pronoun itself is grammatically
inconsistent with something else in the SAME sentence you can point to directly (e.g. "he go"
needs "he goes", or a genuine subject/verb mismatch) — a companion phrase like "with my friends"
is not a reason to change "I" to "we"; the speaker remains the subject.

If the message is fully correct, return an empty errors list. Do not invent errors that are not
present. Respond with the emit_erroranalysisoutput tool using the ErrorAnalysisOutput schema."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": wrap_learner_message(user_message)},
    ]
