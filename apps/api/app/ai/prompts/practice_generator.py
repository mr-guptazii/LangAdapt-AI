from app.ai.prompts.base import SAFETY_PREAMBLE


def build_practice_generation_prompt(
    *, target_language: str, cefr_level: str, skill_name: str, skill_description: str,
    error_examples: list[str], question_types: list[str], count: int,
) -> list[dict]:
    system = f"""{SAFETY_PREAMBLE}

You are the Practice Generator for a {target_language} tutoring system. Generate {count}
exercises targeting the skill "{skill_name}" ({skill_description}) at CEFR {cefr_level}.

{f'''This learner has specifically struggled with: {"; ".join(error_examples)}. Tailor at least
one exercise directly around one of these concrete mistakes.''' if error_examples else ""}

Use a mix of these question types where sensible: {", ".join(question_types)}.
Each exercise must have an unambiguous single correct_answer and a one-sentence explanation.
Do not generate a question nearly identical to another in this batch.

Respond with the emit_practicegenerationoutput tool using the PracticeGenerationOutput schema."""
    return [{"role": "system", "content": system}, {"role": "user", "content": "Generate the exercises."}]
