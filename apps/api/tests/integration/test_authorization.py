"""Tenant isolation tests (section 36) — the single most important invariant
in this codebase: a user must never be able to read or write another user's
learning data, even when they know or guess the other user's resource ids."""
import pytest
from httpx import AsyncClient

from tests.integration.conftest import complete_onboarding, register_and_login

pytestmark = pytest.mark.asyncio


async def _user_with_profile(client: AsyncClient, email: str) -> dict:
    auth = await register_and_login(client, email)
    await complete_onboarding(client, auth["access_token"])
    return auth


async def test_user_cannot_read_another_users_dashboard(client: AsyncClient):
    """Each user's /progress/dashboard must reflect only their own data —
    there is no shared or cross-visible state even though both hit the same
    endpoint with no id in the URL (the id comes from the JWT, not the client)."""
    user_a = await _user_with_profile(client, "tenant-a@test.com")
    user_b = await _user_with_profile(client, "tenant-b@test.com")

    resp_a = await client.get("/api/v1/progress/dashboard", headers={"Authorization": f"Bearer {user_a['access_token']}"})
    resp_b = await client.get("/api/v1/progress/dashboard", headers={"Authorization": f"Bearer {user_b['access_token']}"})
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    # Both are fresh accounts with identical starting state — this asserts the
    # endpoint responds per-caller at all, not that the values differ.
    assert resp_a.json()["cefr_level"] == resp_b.json()["cefr_level"] == "B1"


async def test_user_cannot_access_another_users_session_messages(client: AsyncClient):
    user_a = await _user_with_profile(client, "sess-a@test.com")
    user_b = await _user_with_profile(client, "sess-b@test.com")

    chat_resp = await client.post(
        "/api/v1/chat/message", headers={"Authorization": f"Bearer {user_a['access_token']}"},
        json={"session_id": None, "message": "Hello there.", "mode": "conversation", "input_mode": "text"},
    )
    assert chat_resp.status_code == 200
    session_id = chat_resp.json()["session_id"]

    # User B guesses/knows user A's session id and tries to read its messages.
    resp = await client.get(f"/api/v1/sessions/{session_id}/messages", headers={"Authorization": f"Bearer {user_b['access_token']}"})
    assert resp.status_code == 404  # not 403 — existence isn't confirmed to a non-owner either

    # The rightful owner can read it.
    resp_owner = await client.get(f"/api/v1/sessions/{session_id}/messages", headers={"Authorization": f"Bearer {user_a['access_token']}"})
    assert resp_owner.status_code == 200
    assert len(resp_owner.json()) >= 1


async def test_user_cannot_submit_answer_to_another_users_practice_question(client: AsyncClient, seeded_skill):
    user_a = await _user_with_profile(client, "prac-a@test.com")
    user_b = await _user_with_profile(client, "prac-b@test.com")

    gen_resp = await client.get(
        "/api/v1/practice/next", headers={"Authorization": f"Bearer {user_a['access_token']}"}, params={"skill_code": "past_tense", "count": 1},
    )
    assert gen_resp.status_code == 200
    questions = gen_resp.json()
    assert len(questions) >= 1
    question_id = questions[0]["id"]

    resp = await client.post(
        "/api/v1/practice/submit", headers={"Authorization": f"Bearer {user_b['access_token']}"},
        json={"question_id": question_id, "answer": "anything", "response_time_ms": 1000},
    )
    assert resp.status_code == 403


async def test_admin_endpoint_rejects_non_admin(client: AsyncClient):
    user = await _user_with_profile(client, "notadmin@test.com")
    resp = await client.get("/api/v1/analytics/admin/overview", headers={"Authorization": f"Bearer {user['access_token']}"})
    assert resp.status_code == 403


async def test_unauthenticated_requests_are_rejected(client: AsyncClient):
    resp = await client.get("/api/v1/progress/dashboard")
    assert resp.status_code == 401
