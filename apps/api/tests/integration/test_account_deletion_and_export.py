"""Real data export and real account deletion — see app/api/v1/settings.py.
Previously export claimed an email that no email integration in this
codebase could send, and deletion only flipped is_active=False rather than
actually removing the account's data."""
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.errors import LearnerError
from app.models.learner import LearnerProfile
from app.models.mastery import SkillMastery
from app.models.session import LearningSession, Message
from app.models.system import AuditLog
from app.models.user import Profile, User
from tests.integration.conftest import complete_onboarding, register_and_login

MISTAKE_MESSAGE = "Yesterday I go to college and buy some food."


async def test_export_contains_real_reflected_data(client: AsyncClient):
    auth = await register_and_login(client, "export-real@example.com")
    token = auth["access_token"]
    await complete_onboarding(client, token)

    resp = await client.post(
        "/api/v1/chat/message", headers={"Authorization": f"Bearer {token}"},
        json={"message": MISTAKE_MESSAGE, "mode": "conversation"},
    )
    assert resp.status_code == 200, resp.text

    export = await client.post("/api/v1/settings/export", headers={"Authorization": f"Bearer {token}"})
    assert export.status_code == 200
    body = export.json()

    assert body["account"]["email"] == "export-real@example.com"
    assert body["learner_profile"]["target_language_code"] == "en"
    assert any(s["messages"] for s in body["sessions"]), "export should include the real conversation just had"
    assert any(e["category"] == "past_tense" for e in body["errors"]), "export should include the real detected error"


async def test_account_deletion_removes_owned_data_and_keeps_audit_trail(client: AsyncClient, db_session: AsyncSession):
    auth = await register_and_login(client, "delete-real@example.com")
    token = auth["access_token"]
    user_id = auth["user_id"]
    await complete_onboarding(client, token)

    resp = await client.post(
        "/api/v1/chat/message", headers={"Authorization": f"Bearer {token}"},
        json={"message": MISTAKE_MESSAGE, "mode": "conversation"},
    )
    assert resp.status_code == 200, resp.text

    profile = (await db_session.execute(select(LearnerProfile).where(LearnerProfile.user_id == user_id))).scalar_one()
    profile_id = profile.id

    delete_resp = await client.delete("/api/v1/settings/account", headers={"Authorization": f"Bearer {token}"})
    assert delete_resp.status_code == 200
    assert delete_resp.json()["status"] == "account_deleted"

    # The user row itself is gone — not just deactivated.
    assert await db_session.get(User, user_id) is None
    profile_rows = (await db_session.execute(select(Profile).where(Profile.user_id == user_id))).scalars().all()
    assert profile_rows == []

    # Every owned child row cascaded away with it.
    assert (await db_session.get(LearnerProfile, profile_id)) is None
    errors = (await db_session.execute(select(LearnerError).where(LearnerError.learner_profile_id == profile_id))).scalars().all()
    assert errors == []
    mastery = (await db_session.execute(select(SkillMastery).where(SkillMastery.learner_profile_id == profile_id))).scalars().all()
    assert mastery == []
    sessions = (await db_session.execute(select(LearningSession).where(LearningSession.user_id == user_id))).scalars().all()
    assert sessions == []
    messages = (await db_session.execute(
        select(Message).join(LearningSession, Message.session_id == LearningSession.id).where(LearningSession.user_id == user_id)
    )).scalars().all()
    assert messages == []

    # The audit trail survives the deletion, with the actor reference cleared.
    audit_rows = (await db_session.execute(select(AuditLog).where(AuditLog.action == "account.delete"))).scalars().all()
    matching = [a for a in audit_rows if a.meta.get("deleted_user_id") == str(user_id)]
    assert len(matching) == 1
    assert matching[0].actor_user_id is None


async def test_deleted_account_cannot_log_in_again(client: AsyncClient):
    auth = await register_and_login(client, "delete-then-login@example.com", password="testpass123")
    token = auth["access_token"]
    await complete_onboarding(client, token)

    delete_resp = await client.delete("/api/v1/settings/account", headers={"Authorization": f"Bearer {token}"})
    assert delete_resp.status_code == 200

    login_resp = await client.post("/api/v1/auth/login", json={"email": "delete-then-login@example.com", "password": "testpass123"})
    assert login_resp.status_code == 401
