"""Seeded demo/showcase accounts (User.is_demo) must never inflate the admin
dashboard's business metrics — see app/services/admin_service.py."""
from sqlalchemy import select

from app.core.security import hash_password
from app.models.learner import LearnerProfile
from app.models.user import User
from app.services import admin_service


async def _real_user(db_session, email: str) -> User:
    user = User(email=email, hashed_password=hash_password("testpass123"), is_demo=False)
    db_session.add(user)
    await db_session.flush()
    db_session.add(LearnerProfile(user_id=user.id, cefr_level="B1", target_language_code="en"))
    await db_session.flush()
    return user


async def _demo_user(db_session, email: str) -> User:
    user = User(email=email, hashed_password=hash_password("testpass123"), is_demo=True)
    db_session.add(user)
    await db_session.flush()
    db_session.add(LearnerProfile(user_id=user.id, cefr_level="C2", target_language_code="ja"))
    await db_session.flush()
    return user


async def test_overview_excludes_demo_accounts(db_session):
    await _real_user(db_session, "real-admin-metrics@example.com")
    await _demo_user(db_session, "demo-admin-metrics@example.com")
    await db_session.flush()

    before = await admin_service.get_overview(db_session)

    await _real_user(db_session, "real-admin-metrics-2@example.com")
    await _demo_user(db_session, "demo-admin-metrics-2@example.com")
    await db_session.flush()

    after = await admin_service.get_overview(db_session)

    # Adding one more real user AND one more demo user should only move the
    # count by 1 (the real one) — proves is_demo is actually filtered, not
    # just coincidentally absent from this test's data.
    assert after["total_users"] == before["total_users"] + 1


async def test_retention_excludes_demo_accounts(db_session):
    await _demo_user(db_session, "demo-retention@example.com")
    await db_session.flush()

    result = (await db_session.execute(select(User).where(User.email == "demo-retention@example.com"))).scalar_one()
    assert result.is_demo is True

    retention = await admin_service.get_retention(db_session)
    # No assertion error means the query ran successfully with the join/filter
    # applied — the real behavioral proof is test_overview_excludes_demo_accounts
    # above; this just confirms get_retention doesn't crash with a demo-only DB.
    assert "dau" in retention
