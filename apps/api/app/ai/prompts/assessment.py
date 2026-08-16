from app.ai.prompts.base import SAFETY_PREAMBLE

_SKILL_GUIDANCE = {
    # The learner sees ONLY the `prompt` field (plus `options`, for multiple_choice) —
    # nothing else renders on screen. Every instruction below exists because a model
    # left unguided will write a meta-reference ("read the following text...", "what
    # does the expression [mean]") without actually including the thing it refers to,
    # or fall back to placeholder options ("A", "B", "C", "D") — both observed live
    # in production, across multiple skill areas.
    "vocabulary": (
        "`prompt` MUST test the meaning, synonym, or correct usage of one specific word, "
        "phrase, or idiom, spelled out in full inside the question text itself — e.g. "
        "\"What does the expression 'break the ice' mean?\", never \"What does the "
        "expression [mean]?\" with the expression itself missing. Never ask a general-"
        "knowledge or opinion question (e.g. \"What is the correct time to go to bed?\") "
        "that isn't actually about a word's meaning or usage."
    ),
    "grammar": (
        "`prompt` MUST test one specific, identifiable grammar point (e.g. verb tense, "
        "subject-verb agreement, articles, prepositions, comparatives, word order), "
        "framed as either a fill-in-the-blank sentence or a \"choose the correct "
        "sentence\" question, with the actual example sentence spelled out in full inside "
        "the question text itself — never refer to \"the sentence\" or \"the example\" "
        "without those words actually being present. Never ask a general-knowledge or "
        "opinion question (e.g. \"What is the correct time to go to bed?\") that has "
        "nothing to do with grammar."
    ),
    "reading": (
        'The `prompt` field MUST be fully self-contained: write a short passage (3-6 '
        "sentences, appropriate for this CEFR level) directly inside `prompt`, followed "
        "by a comprehension question about it. Never write a meta-reference like 'read "
        "the following text' or 'this passage' without the passage's actual words being "
        "part of `prompt` — there is no separate passage field."
    ),
    "listening": (
        "There is no audio playback in this assessment, so the `prompt` field MUST open "
        "with a short spoken-style passage written out as text (3-5 sentences, framed as "
        "something someone said or announced), followed by a comprehension question about "
        "it. Never reference audio the learner can't actually hear."
    ),
    "writing": (
        "Use question_type \"free_response\". `prompt` should ask the learner to write a "
        "short response (1-3 sentences) demonstrating a specific grammar point or "
        "vocabulary use at this level. correct_answer should describe the key criteria a "
        "correct answer must include, not one fixed string."
    ),
    "speaking": (
        "Use question_type \"free_response\". `prompt` should ask the learner to say a "
        "short spoken response (1-2 sentences) aloud. correct_answer should describe the "
        "key criteria a correct answer must include, not one fixed string."
    ),
}


def build_assessment_question_prompt(*, target_language: str, skill_area: str, difficulty: str) -> list[dict]:
    guidance = _SKILL_GUIDANCE.get(skill_area, "")
    system = f"""{SAFETY_PREAMBLE}

You are the Adaptive Assessment component for {target_language}. Generate ONE placement-test
question for skill area "{skill_area}" at CEFR difficulty {difficulty}. Prefer multiple_choice
with exactly 4 options and one unambiguous correct_answer, unless skill_area is "writing" or
"speaking", in which case use a free_response prompt instead.

The learner sees ONLY the `prompt` field (and `options`, for multiple_choice) — there is no
separate passage/word/sentence field and nothing else renders on screen. `prompt` must be fully
self-contained: never refer to a word, expression, sentence, or text ("the expression above",
"this sentence", "the following text") without its exact words actually being written out
inside `prompt` itself.

{guidance}

For multiple_choice questions: every option must be a complete, substantive answer choice
written out in full — never a bare letter like "A"/"B"/"C"/"D" and never a placeholder — and
one of them must exactly match correct_answer.

Respond with the emit_generatedexercise tool using the GeneratedExercise schema
(question_type should be "multiple_choice" or "free_response")."""
    return [{"role": "system", "content": system}, {"role": "user", "content": "Generate the question."}]


def build_learner_model_summary_prompt(*, events: list[dict]) -> list[dict]:
    """Used by the (background, strong-model) learner-model summarization pass —
    section 8/120 — to turn a batch of raw learning events into a structured,
    human-readable memory statement, not raw chat dump."""
    system = f"""{SAFETY_PREAMBLE}

You are the Learner Model summarizer. Given a batch of recent learning events (errors made,
exercises completed, topics discussed), write 1-3 short, concrete memory statements a tutor
would find useful later, e.g. "User frequently confuses present perfect and simple past" or
"User performs noticeably better on grammar when practiced through conversation rather than
multiple-choice." Do not restate raw events; synthesize a pattern. If no clear pattern exists,
return an empty list.

Events: {events}

Respond with the emit_learnermemorybatch tool."""
    return [{"role": "system", "content": system}, {"role": "user", "content": "Summarize."}]
