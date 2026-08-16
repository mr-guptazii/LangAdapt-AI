"""Proves personalization actually changes system behavior for two learners
with different profiles, not just that preference fields exist in the DB.

DEMO LEARNER A: B1, strong vocabulary, weak past tense, prefers conversation,
prefers short explanations.
DEMO LEARNER B: B1, strong grammar, weak vocabulary, prefers quizzes, prefers
detailed explanations.

If any of these tests fail, the personalization system is not complete — see
app/services/demo_learners.py for the exact seeded profiles.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes.context import load_learner_context
from app.ai.prompts.conversation import build_conversation_prompt
from app.models.language import Skill
from app.services.demo_learners import create_demo_learner_a, create_demo_learner_b
from app.services.practice_service import generate_practice_for_weakness
from app.services.recommendation_service import _score_candidates

_REQUIRED_SKILLS = [
    {"code": "past_tense", "name": "Past Tense", "category": "grammar", "cefr_level": "A2", "description": "Simple past for completed actions."},
    {"code": "vocabulary_range", "name": "Vocabulary Range", "category": "vocabulary", "cefr_level": "A2", "description": "Breadth of active vocabulary."},
    {"code": "present_perfect", "name": "Present Perfect", "category": "grammar", "cefr_level": "B1", "description": "Present perfect vs. simple past."},
]


@pytest.fixture
async def demo_skills(db_session: AsyncSession):
    skills = {}
    for data in _REQUIRED_SKILLS:
        existing = await db_session.execute(select(Skill).where(Skill.language_code == "en", Skill.code == data["code"]))
        skill = existing.scalar_one_or_none()
        if skill is None:
            skill = Skill(language_code="en", **data)
            db_session.add(skill)
            await db_session.flush()
        skills[data["code"]] = skill
    return skills


async def _make_learners(db_session: AsyncSession, demo_skills):
    user_a, profile_a = await create_demo_learner_a(db_session)
    user_b, profile_b = await create_demo_learner_b(db_session)
    await db_session.flush()
    return (user_a, profile_a), (user_b, profile_b)


async def test_learner_context_loads_different_personality_and_explanation_length(db_session: AsyncSession, demo_skills):
    (user_a, profile_a), (user_b, profile_b) = await _make_learners(db_session, demo_skills)

    ctx_a = await load_learner_context({"learner_profile_id": str(profile_a.id), "user_id": str(user_a.id)}, db_session)
    ctx_b = await load_learner_context({"learner_profile_id": str(profile_b.id), "user_id": str(user_b.id)}, db_session)

    assert ctx_a["learner_profile"]["ai_personality"] == "casual"
    assert ctx_b["learner_profile"]["ai_personality"] == "strict_coach"
    assert ctx_a["learner_profile"]["ai_personality"] != ctx_b["learner_profile"]["ai_personality"]

    assert ctx_a["learning_preferences"]["preferred_explanation_length"] == "short"
    assert ctx_b["learning_preferences"]["preferred_explanation_length"] == "long"


async def test_conversation_prompt_text_diverges_by_personality_and_explanation_length():
    """Direct proof at the prompt-construction layer, independent of what any
    particular LLM (mock or real) does with the prompt — the SYSTEM DECISION of
    what to tell the model must differ per learner."""
    system_a = build_conversation_prompt(
        target_language="English", native_language="Hindi", cefr_level="B1",
        personality="casual", correction_style="balanced", explanation_length="short",
        recent_errors=[], relevant_memories=[], objective=None, scenario=None,
        conversation_history=[], user_message="hi",
    )[0]["content"]
    system_b = build_conversation_prompt(
        target_language="English", native_language="Hindi", cefr_level="B1",
        personality="strict_coach", correction_style="balanced", explanation_length="long",
        recent_errors=[], relevant_memories=[], objective=None, scenario=None,
        conversation_history=[], user_message="hi",
    )[0]["content"]

    assert system_a != system_b
    assert "relaxed and informal" in system_a
    assert "direct, high-expectation" in system_b
    assert "brevity" in system_a.lower()
    assert "depth" in system_b.lower()


async def test_practice_targets_the_actual_weak_skill_per_learner(db_session: AsyncSession, demo_skills):
    (user_a, profile_a), (user_b, profile_b) = await _make_learners(db_session, demo_skills)

    questions_a = await generate_practice_for_weakness(
        db_session, learner_profile=profile_a, skill=demo_skills["past_tense"], count=1, user_id=user_a.id
    )
    questions_b = await generate_practice_for_weakness(
        db_session, learner_profile=profile_b, skill=demo_skills["vocabulary_range"], count=1, user_id=user_b.id
    )

    assert questions_a and questions_b
    assert questions_a[0].skill_id == demo_skills["past_tense"].id
    assert questions_b[0].skill_id == demo_skills["vocabulary_range"].id
    assert questions_a[0].skill_id != questions_b[0].skill_id


async def test_recommendation_candidates_diverge_by_learner_weakness(db_session: AsyncSession, demo_skills):
    (user_a, profile_a), (user_b, profile_b) = await _make_learners(db_session, demo_skills)

    candidates_a = await _score_candidates(db_session, profile_a)
    candidates_b = await _score_candidates(db_session, profile_b)

    top_skill_a = next((c["target_skill_code"] for c in candidates_a if c["reason_code"] == "recent_mistake"), None)
    top_skill_b = next((c["target_skill_code"] for c in candidates_b if c["reason_code"] == "recent_mistake"), None)

    assert top_skill_a == "past_tense"
    assert top_skill_b == "vocabulary_range"
    assert top_skill_a != top_skill_b


async def test_ability_profiles_are_seeded_as_specified(db_session: AsyncSession, demo_skills):
    """Sanity-checks the demo learners themselves match the required spec, so a
    future edit to demo_learners.py that breaks the contract fails loudly here
    rather than producing confusing failures in the divergence tests above."""
    (_, profile_a), (_, profile_b) = await _make_learners(db_session, demo_skills)

    assert profile_a.cefr_level == "B1" and profile_b.cefr_level == "B1"
    assert profile_a.vocabulary_ability > profile_a.grammar_ability  # strong vocab, weak grammar (past tense)
    assert profile_b.grammar_ability > profile_b.vocabulary_ability  # strong grammar, weak vocab
    assert profile_a.vocabulary_ability > profile_b.vocabulary_ability
    assert profile_b.grammar_ability > profile_a.grammar_ability
