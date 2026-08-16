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

Every exercise must test the GRAMMATICAL FORM of "{skill_name}" — never a real-world
opinion/trivia question with no grammatically determinable answer (e.g. "What do people usually
eat for breakfast?" has no single correct answer; "cereal" and "toast" are both valid — that is
not a testable exercise). The learner is graded on producing the grammatically correct sentence,
not on guessing a fact.

Use a mix of these question types where sensible: {", ".join(question_types)}. Rules per type,
each critical to get right (exercises that break these rules are ungradable):
- fill_blank: `prompt` has a blank in a specific sentence with a specific subject already given
  (e.g. "It ______ apples."). `correct_answer` MUST be that exact same full sentence with the
  blank correctly filled in, including the leading subject — never just the words after the
  blank. Given prompt "I ______ my homework yesterday.", correct_answer must be "I finished my
  homework yesterday." — NOT "finished my homework yesterday." (dropping "I" makes it ungradable
  against a learner's full-sentence answer). Never substitute a different subject either.
- correction: `prompt` is a sentence containing exactly one grammar mistake. `correct_answer` is
  that same sentence with only the mistake fixed — everything else stays identical.
- transformation: `prompt` gives one sentence and asks for it restated in a different grammatical
  form (e.g. tense, voice, question form). Every option in `options` MUST be about the exact same
  content/topic as the given sentence — only the grammatical form changes between options, never
  the subject matter (a "video games" sentence must not have "watching TV" as an option; that is
  a different topic entirely, not a valid distractor).
- multiple_choice: `options` are short — just the alternative word or phrase that fills the blank
  (e.g. ["goes", "go", "going", "to go"]), never the whole sentence restated. All options must be
  grammatically plausible completions of the same `prompt`, differing only in the grammar point
  being tested (verb form, word order, article, etc.) — not different unrelated real-world facts,
  and no duplicate options.

Each exercise must have an unambiguous single correct_answer (one of `options`, if present, must
match `correct_answer` exactly) and a one-sentence explanation of the grammar rule involved — not
a fact justification. Do not generate a question nearly identical to another in this batch.

Respond with the emit_practicegenerationoutput tool using the PracticeGenerationOutput schema."""
    return [{"role": "system", "content": system}, {"role": "user", "content": "Generate the exercises."}]
