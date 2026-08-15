"""Automated agent evaluation (section 60). Runs the SAME code paths the
application uses in production (build_error_analysis_prompt +
LLMProvider.structured against ErrorAnalysisOutput) against a curated dataset,
so the eval is exercising real behavior, not a reimplementation of it.
"""
from dataclasses import dataclass, field

from app.ai.prompts.error_analysis import build_error_analysis_prompt
from app.ai.providers.base import LLMMessage, LLMProvider, ModelTier
from app.evaluation.datasets import ERROR_ANALYSIS_CASES, RECOMMENDATION_CASES, ErrorAnalysisEvalCase, RecommendationEvalCase
from app.evaluation.metrics import PRF1, precision_recall_f1
from app.schemas.agent_io import ErrorAnalysisOutput


@dataclass
class ErrorAnalysisCaseResult:
    case: ErrorAnalysisEvalCase
    predicted_categories: list[str]
    passed: bool  # exact multiset match against expected_categories
    hallucinated: bool  # expected no errors but got at least one


@dataclass
class ErrorAnalysisEvalReport:
    provider_name: str
    results: list[ErrorAnalysisCaseResult]
    aggregate: PRF1
    hallucination_rate: float
    pass_rate: float = field(init=False)

    def __post_init__(self):
        self.pass_rate = round(sum(1 for r in self.results if r.passed) / len(self.results), 3) if self.results else 0.0


async def run_error_analysis_eval(provider: LLMProvider, cases: list[ErrorAnalysisEvalCase] | None = None) -> ErrorAnalysisEvalReport:
    cases = cases if cases is not None else ERROR_ANALYSIS_CASES
    all_expected: list[str] = []
    all_predicted: list[str] = []
    results: list[ErrorAnalysisCaseResult] = []
    hallucinations = 0
    clean_case_count = 0

    for case in cases:
        messages = build_error_analysis_prompt(target_language="English", cefr_level="B1", user_message=case.input_text)
        llm_messages = [LLMMessage(role=m["role"], content=m["content"]) for m in messages]
        output, _usage = await provider.structured(llm_messages, ErrorAnalysisOutput, tier=ModelTier.FAST, max_tokens=500)

        predicted_categories = [e.category for e in output.errors]
        all_expected.extend(case.expected_categories)
        all_predicted.extend(predicted_categories)

        passed = sorted(predicted_categories) == sorted(case.expected_categories)
        is_clean_case = len(case.expected_categories) == 0
        hallucinated = is_clean_case and len(predicted_categories) > 0
        if is_clean_case:
            clean_case_count += 1
        if hallucinated:
            hallucinations += 1

        results.append(ErrorAnalysisCaseResult(case=case, predicted_categories=predicted_categories, passed=passed, hallucinated=hallucinated))

    aggregate = precision_recall_f1(all_expected, all_predicted)
    hallucination_rate = round(hallucinations / clean_case_count, 3) if clean_case_count else 0.0

    return ErrorAnalysisEvalReport(provider_name=provider.name, results=results, aggregate=aggregate, hallucination_rate=hallucination_rate)


@dataclass
class RecommendationCaseResult:
    case: RecommendationEvalCase
    weak_skill_priority: float
    passed: bool


def evaluate_recommendation_ranking(cases: list[RecommendationEvalCase] | None = None) -> list[RecommendationCaseResult]:
    """Deterministic, no LLM / no DB required — evaluates the ranking FORMULA
    itself (mirrors app/services/recommendation_service.py::_score_candidates;
    keep the constants below in sync with that function)."""
    cases = cases if cases is not None else RECOMMENDATION_CASES
    results = []
    for case in cases:
        weak_skill_priority = 0.5 + case.weak_skill_weakness_score * 0.4  # recent_mistake candidate formula
        due_review_priority = 0.55 if case.has_due_review else 0.0
        goal_alignment_priority = 0.45  # always-present variety candidate

        ranked_first = weak_skill_priority > due_review_priority and weak_skill_priority > goal_alignment_priority
        passed = ranked_first == case.expect_weak_skill_ranked_first
        results.append(RecommendationCaseResult(case=case, weak_skill_priority=round(weak_skill_priority, 3), passed=passed))
    return results
