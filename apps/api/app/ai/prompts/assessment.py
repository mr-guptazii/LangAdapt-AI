from app.ai.prompts.base import SAFETY_PREAMBLE


def build_assessment_question_prompt(*, target_language: str, skill_area: str, difficulty: str) -> list[dict]:
    system = f"""{SAFETY_PREAMBLE}

You are the Adaptive Assessment component for {target_language}. Generate ONE placement-test
question for skill area "{skill_area}" at CEFR difficulty {difficulty}. Prefer multiple_choice
with exactly 4 options and one unambiguous correct_answer, unless skill_area is "writing" or
"speaking", in which case use a free_response prompt instead (correct_answer should describe
the key criteria a correct answer must include).

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
