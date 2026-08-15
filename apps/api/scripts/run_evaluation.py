"""Run the agent evaluation suite and print a human-readable report.

Usage (from apps/api, with the venv active):
    python scripts/run_evaluation.py

Uses whichever LLM_PROVIDER is configured in the environment (mock by
default). Point it at a real provider to see production-quality accuracy:
    LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=... python scripts/run_evaluation.py
"""
import asyncio

from app.ai.providers.factory import get_llm_provider
from app.evaluation.runner import evaluate_recommendation_ranking, run_error_analysis_eval


async def main():
    provider = get_llm_provider()
    print(f"=== Error Analysis Agent Evaluation (provider: {provider.name}) ===\n")

    report = await run_error_analysis_eval(provider)
    for result in report.results:
        status = "PASS" if result.passed else ("HALLUCINATION" if result.hallucinated else "FAIL")
        print(f"[{status:14}] {result.case.id}")
        print(f"                 input:    {result.case.input_text}")
        print(f"                 expected: {result.case.expected_categories}")
        print(f"                 got:      {result.predicted_categories}")
        if result.case.note:
            print(f"                 note:     {result.case.note}")
        print()

    print(f"Pass rate:          {report.pass_rate * 100:.1f}%")
    print(f"Hallucination rate: {report.hallucination_rate * 100:.1f}% (errors flagged on clean sentences)")
    print(f"Precision:          {report.aggregate.precision}")
    print(f"Recall:             {report.aggregate.recall}")
    print(f"F1:                 {report.aggregate.f1}")

    print("\n=== Recommendation Ranking Evaluation (deterministic, no LLM) ===\n")
    rec_results = evaluate_recommendation_ranking()
    for r in rec_results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.case.id} (weak_skill_priority={r.weak_skill_priority}) — {r.case.note}")

    rec_pass_rate = sum(1 for r in rec_results if r.passed) / len(rec_results)
    print(f"\nPass rate: {rec_pass_rate * 100:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
