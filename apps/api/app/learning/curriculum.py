"""Curriculum graph (section 91/92). Maps CEFR levels to skill codes for a given
target language. The adaptation/recommendation engines consult this to know what
"the next thing" could be, but learners are never forced through it in a fixed
sequence — see recommendation engine's ranking, which balances this against
actual observed weakness/goals/variety.
"""
from app.learning.languages.en.grammar_topics import EN_SKILLS

CURRICULUM_BY_LANGUAGE: dict[str, list[dict]] = {
    "en": EN_SKILLS,
}

CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


def get_curriculum(language_code: str) -> list[dict]:
    return CURRICULUM_BY_LANGUAGE.get(language_code, EN_SKILLS)


def next_cefr_level(level: str) -> str:
    if level not in CEFR_ORDER:
        return level
    idx = CEFR_ORDER.index(level)
    return CEFR_ORDER[min(idx + 1, len(CEFR_ORDER) - 1)]


def previous_cefr_level(level: str) -> str:
    if level not in CEFR_ORDER:
        return level
    idx = CEFR_ORDER.index(level)
    return CEFR_ORDER[max(idx - 1, 0)]
