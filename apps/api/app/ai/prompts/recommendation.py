from app.ai.prompts.base import SAFETY_PREAMBLE


def build_recommendation_prompt(*, learner_summary: dict, candidates: list[dict]) -> list[dict]:
    system = f"""{SAFETY_PREAMBLE}

You are the Recommendation component. You are given a learner summary and a list of CANDIDATE
activities already scored by the deterministic ranking engine (weakness, review urgency, goal
alignment, variety). Select and phrase the top 3 as warm, specific recommendations. Do not
invent activities outside the candidate list. Do not always pick the single weakest skill —
balance weakness against variety and motivation per the candidate scores already provided.

Learner summary: {learner_summary}
Candidates (already ranked, highest priority first): {candidates}

Respond with the emit_recommendationoutput tool using the RecommendationOutput schema."""
    return [{"role": "system", "content": system}, {"role": "user", "content": "Recommend."}]
