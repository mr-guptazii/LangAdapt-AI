"""Curated evaluation dataset for the Error Analysis Agent (section 60).

Each case is a learner sentence with the errors a competent tutor should (or,
for clean sentences, should NOT) detect. Categories are deliberately mixed:
grammar cases the bundled MockLLMProvider is documented to catch (past-tense,
via app/ai/providers/mock_provider.py's _PAST_TENSE_MAP) sit alongside cases
outside its narrow scope (articles, prepositions, subject-verb agreement) and
a "clean sentence" hallucination check. Running this dataset against the mock
provider is expected to show partial recall — that's the honest, correct
result for a rule-based stand-in, not a bug in the eval framework. Point
LLM_PROVIDER at a real model to see how a production configuration performs.
"""
from dataclasses import dataclass, field


@dataclass
class ErrorAnalysisEvalCase:
    id: str
    input_text: str
    expected_categories: list[str]  # empty list = expect NO errors detected (hallucination check)
    note: str = ""


ERROR_ANALYSIS_CASES: list[ErrorAnalysisEvalCase] = [
    ErrorAnalysisEvalCase(
        id="past_tense_simple",
        input_text="Yesterday I go to the market.",
        expected_categories=["past_tense"],
        note="Canonical past-tense case; mock provider is expected to catch this.",
    ),
    ErrorAnalysisEvalCase(
        id="past_tense_multiple",
        input_text="Yesterday I go to the market and buy some fruits.",
        expected_categories=["past_tense", "past_tense"],
        note="Two irregular verbs in one sentence — tests recall, not just detection.",
    ),
    ErrorAnalysisEvalCase(
        id="past_tense_with_have",
        input_text="I have go to the office yesterday.",
        expected_categories=["past_tense"],
        note="Section 63's exact demo scenario line 3 ('I have go yesterday').",
    ),
    ErrorAnalysisEvalCase(
        id="clean_sentence_present",
        input_text="I go to the gym every morning before work.",
        expected_categories=[],
        note="Hallucination check (section 90): 'go' is CORRECT here (present habitual, no past-tense signal word) — must not be flagged.",
    ),
    ErrorAnalysisEvalCase(
        id="clean_sentence_correct_past",
        input_text="Yesterday I went to the market and bought some fruit.",
        expected_categories=[],
        note="Hallucination check: already-correct past tense must not be flagged as an error.",
    ),
    ErrorAnalysisEvalCase(
        id="article_error",
        input_text="I saw elephant at the zoo yesterday.",
        expected_categories=["articles"],
        note="Missing article before a countable singular noun — outside the mock provider's documented scope (AI_SYSTEM.md); expected to be a real-provider-only pass.",
    ),
    ErrorAnalysisEvalCase(
        id="preposition_error",
        input_text="I am interested on learning new languages.",
        expected_categories=["prepositions"],
        note="'interested on' -> 'interested in'; outside the mock provider's documented scope.",
    ),
    ErrorAnalysisEvalCase(
        id="subject_verb_agreement",
        input_text="She go to school every day.",
        expected_categories=["subject_verb_agreement"],
        note="Third-person singular needs 'goes'; outside the mock provider's documented scope.",
    ),
]


@dataclass
class RecommendationEvalCase:
    """Section 60: personalization / difficulty-adaptation evaluation. Checks
    that the DETERMINISTIC ranking layer (app/services/recommendation_service.py
    ._score_candidates), not the LLM, prioritizes weak/due skills over a
    generic goal-alignment filler — the property that must hold regardless of
    which LLM_PROVIDER phrases the final text."""
    id: str
    weak_skill_weakness_score: float
    has_due_review: bool
    expect_weak_skill_ranked_first: bool
    note: str = field(default="")


RECOMMENDATION_CASES: list[RecommendationEvalCase] = [
    RecommendationEvalCase(
        id="strong_weakness_outranks_goal_filler",
        weak_skill_weakness_score=0.9, has_due_review=False, expect_weak_skill_ranked_first=True,
        note="A severe, recent weakness should rank above the generic goal-alignment conversation suggestion.",
    ),
    RecommendationEvalCase(
        id="due_review_outranks_a_very_mild_weakness",
        weak_skill_weakness_score=0.05, has_due_review=True, expect_weak_skill_ranked_first=False,
        note="Section 87: balance, not always-weakest — a spaced-repetition item that's actually due should "
             "outrank a barely-registered mistake (priority 0.55 vs ~0.52). Demonstrates the ranking engine "
             "isn't a pure 'always recommend the weakest thing' rule.",
    ),
]
