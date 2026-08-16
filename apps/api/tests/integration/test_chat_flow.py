"""End-to-end verification of the core agentic differentiator (section 123):
a learner message with a real grammar mistake runs through the full LangGraph
pipeline, gets detected by the mock provider, and the resulting mastery/error
state is actually persisted — not just reflected in the HTTP response."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.errors import LearnerError
from app.models.learner import LearnerProfile
from app.models.mastery import SkillMastery
from tests.integration.conftest import complete_onboarding, register_and_login

pytestmark = pytest.mark.asyncio


async def _onboarded_user(client: AsyncClient, email: str) -> dict:
    auth = await register_and_login(client, email)
    await complete_onboarding(client, auth["access_token"])
    return auth


async def test_routine_message_skips_the_heavy_pipeline(client: AsyncClient):
    """No grammar mistake -> the routing in agents/graph.py should skip the
    learner-model/adaptation/teaching-strategy nodes (section 42 cost routing)."""
    user = await _onboarded_user(client, "chat-routine@test.com")
    resp = await client.post(
        "/api/v1/chat/message", headers={"Authorization": f"Bearer {user['access_token']}"},
        json={"session_id": None, "message": "Hello, how are you today?", "mode": "conversation", "input_mode": "text"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["corrections"] == []
    assert "learner_model_agent" not in body["agents_invoked"]
    assert "adaptation_agent" not in body["agents_invoked"]
    assert "conversation_agent" in body["agents_invoked"]


async def test_past_tense_error_is_detected_and_persisted(client: AsyncClient, seeded_skill, db_session):
    user = await _onboarded_user(client, "chat-error@test.com")
    resp = await client.post(
        "/api/v1/chat/message", headers={"Authorization": f"Bearer {user['access_token']}"},
        json={"session_id": None, "message": "Yesterday I go to the market and buy some fruits.", "mode": "conversation", "input_mode": "text"},
    )
    assert resp.status_code == 200
    body = resp.json()

    # The response itself reflects the detection.
    assert len(body["corrections"]) >= 1
    categories = {c["category"] for c in body["corrections"]}
    assert "past_tense" in categories
    assert "error_analysis_agent" in body["agents_invoked"]
    assert "learner_model_agent" in body["agents_invoked"]  # significant-event path taken

    # And it's really in the database, not just echoed back in the response.
    # Scoped to THIS user's learner_profile_id — an unscoped query here was
    # fragile against any dev database that also has a pre-existing learner
    # with a past_tense error (e.g. the demo account from scripts/seed.py),
    # which would make .scalar_one_or_none() raise MultipleResultsFound.
    profile = (await db_session.execute(select(LearnerProfile).where(LearnerProfile.user_id == user["user_id"]))).scalar_one()
    error_row = (await db_session.execute(
        select(LearnerError).where(LearnerError.learner_profile_id == profile.id, LearnerError.category == "past_tense")
    )).scalar_one_or_none()
    assert error_row is not None
    assert error_row.occurrence_count >= 1

    mastery_row = (await db_session.execute(
        select(SkillMastery).where(SkillMastery.learner_profile_id == profile.id, SkillMastery.skill_id == seeded_skill.id)
    )).scalar_one_or_none()
    assert mastery_row is not None
    assert mastery_row.attempts >= 1


async def test_session_persists_across_multiple_turns(client: AsyncClient):
    user = await _onboarded_user(client, "chat-session@test.com")
    first = await client.post(
        "/api/v1/chat/message", headers={"Authorization": f"Bearer {user['access_token']}"},
        json={"session_id": None, "message": "Hi!", "mode": "conversation", "input_mode": "text"},
    )
    session_id = first.json()["session_id"]

    second = await client.post(
        "/api/v1/chat/message", headers={"Authorization": f"Bearer {user['access_token']}"},
        json={"session_id": session_id, "message": "Let's keep talking.", "mode": "conversation", "input_mode": "text"},
    )
    assert second.status_code == 200
    assert second.json()["session_id"] == session_id

    messages = await client.get(f"/api/v1/sessions/{session_id}/messages", headers={"Authorization": f"Bearer {user['access_token']}"})
    assert messages.status_code == 200
    assert len(messages.json()) == 4  # 2 user + 2 assistant turns
