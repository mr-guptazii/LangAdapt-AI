from app.ai.prompts.base import SAFETY_PREAMBLE, wrap_learner_message
from app.learning.languages.en.grammar_topics import EN_SKILLS

# The real, curated skill taxonomy (app/models/mastery.py rows are keyed off
# these exact codes). error_analysis_agent's `category` field used to be
# free text with only a loose example list — the model would readily invent
# a natural-sounding code like "vocabulary" that was never actually seeded
# (the real code is "vocabulary_range"), and any downstream lookup by that
# category (e.g. /practice/next's "give me practice for my weakest skill")
# would silently fail to find a matching skill. Constraining the prompt to
# this exact list is the fix at the source; app/api/v1/practice.py also got
# a defensive fallback for any category that still doesn't match, since an
# LLM's output should never be trusted as a guaranteed foreign key.
_VALID_CATEGORIES = ", ".join(s["code"] for s in EN_SKILLS)


def build_error_analysis_prompt(
    *, target_language: str, cefr_level: str, user_message: str, conversation_history: list[dict] | None = None
) -> list[dict]:
    history_block = ""
    if conversation_history:
        recent = conversation_history[-6:]
        transcript = "\n".join(f"{'Learner' if t['role'] == 'user' else 'Tutor'}: {t['content']}" for t in recent)
        history_block = f"""
Recent conversation so far (use this to resolve what the learner's new message actually means —
e.g. if earlier turns already established the learner is recounting something that already
happened, a later bare-present-tense verb with no new time marker is almost always still part of
that same past-tense narrative, not a new statement about the present or future):
{transcript}
"""

    system = f"""{SAFETY_PREAMBLE}

You are the Error Analysis component of a {target_language} tutoring system. Analyze the
learner's NEW message (CEFR {cefr_level}) for grammar, vocabulary, spelling, and register
mistakes. Find EVERY distinct real mistake present, not just the most obvious one — a single
message can have a tense error, a spelling error, and a capitalization error all at once; report
each as its own entry rather than stopping after the first one you notice.
{history_block}
For each mistake found:
- type: grammar|vocabulary|spelling|fluency
- category: MUST be exactly one of these codes (pick the closest match, never invent a new one):
  {_VALID_CATEGORIES}, spelling, capitalization
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
going to"). The same applies even without a fresh time marker if the conversation history above
already established a past-tense narrative — a bare-present verb ("I buy...", "I see...") that
continues that same story is still a past-tense mistake ("I bought...", "I saw..."), not a
separate present-tense statement. Default to the past-tense reading; do not propose present
continuous ("I'm going") as the fix unless a future marker is actually present.

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
