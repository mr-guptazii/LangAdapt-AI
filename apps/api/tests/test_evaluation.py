"""Runs the agent evaluation framework (section 60) as part of the automated
suite, against the mock provider (the same one CI and local dev use with no
API key). Thresholds are calibrated to the mock provider's DOCUMENTED, narrow
scope (see app/ai/providers/mock_provider.py and app/evaluation/datasets.py) —
they intentionally do not demand 100% recall on categories the mock provider
was never built to detect (articles/prepositions/subject-verb agreement).
What they DO strictly demand: zero hallucinations, and full recall on the
cases the mock provider is documented to handle (past tense).
"""
import pytest

from app.ai.providers.mock_provider import MockLLMProvider
from app.evaluation.datasets import ERROR_ANALYSIS_CASES
from app.evaluation.runner import evaluate_recommendation_ranking, run_error_analysis_eval

pytestmark = pytest.mark.asyncio


async def test_mock_provider_has_zero_hallucinations_on_clean_sentences():
    """Section 90: never confidently teach an error that isn't there."""
    report = await run_error_analysis_eval(MockLLMProvider())
    assert report.hallucination_rate == 0.0, [r.case.id for r in report.results if r.hallucinated]


async def test_mock_provider_fully_recalls_its_documented_scope():
    """Restrict to just the past-tense cases the mock provider is documented
    to handle — this must be 100%, since it's rule-based and deterministic,
    not a fuzzy model making judgment calls."""
    past_tense_cases = [c for c in ERROR_ANALYSIS_CASES if c.id.startswith("past_tense")]
    report = await run_error_analysis_eval(MockLLMProvider(), cases=past_tense_cases)
    assert report.pass_rate == 1.0, [(r.case.id, r.predicted_categories) for r in report.results if not r.passed]


async def test_full_dataset_pass_rate_is_at_least_the_mock_providers_known_floor():
    """Full dataset includes categories outside the mock provider's scope by
    design (see datasets.py) — this asserts it doesn't regress below what it
    currently covers (5 of 8 cases: all three past-tense cases plus both
    clean-sentence hallucination checks), not that it achieves full coverage —
    the remaining 3 (articles/prepositions/subject-verb agreement) require a
    real LLM_PROVIDER, which this floor deliberately does not require."""
    report = await run_error_analysis_eval(MockLLMProvider())
    assert report.pass_rate >= 0.625, f"pass_rate dropped to {report.pass_rate}"


async def test_recommendation_ranking_formula_is_correct():
    """Deterministic — must be 100%, this isn't an LLM judgment call."""
    results = evaluate_recommendation_ranking()
    assert all(r.passed for r in results), [(r.case.id, r.weak_skill_priority) for r in results if not r.passed]
