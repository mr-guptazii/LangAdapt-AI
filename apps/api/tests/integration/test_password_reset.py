"""Real password-reset flow — see app/services/auth_service.py's
request_password_reset/reset_password. No email transport is wired up yet
(see CLAUDE.md), so these tests create tokens directly the same way the
service layer does, rather than trying to intercept an email that's never
sent."""
from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_reset_token, hash_password
from app.models.system import PasswordResetToken
from app.models.user import User
from app.services.auth_service import request_password_reset, reset_password
from tests.integration.conftest import register_and_login


async def test_forgot_password_response_identical_for_existing_and_nonexistent_email(client: AsyncClient):
    """The single most important property of this endpoint: it must not leak
    whether an email has an account (a classic user-enumeration bug)."""
    await register_and_login(client, "resetflow@example.com")

    resp_exists = await client.post("/api/v1/auth/forgot-password", json={"email": "resetflow@example.com"})
    resp_missing = await client.post("/api/v1/auth/forgot-password", json={"email": "definitely-not-registered@example.com"})

    assert resp_exists.status_code == 200
    assert resp_missing.status_code == 200
    assert resp_exists.json() == resp_missing.json()


async def test_forgot_password_creates_a_real_hashed_token(client: AsyncClient, db_session: AsyncSession):
    auth = await register_and_login(client, "creates-token@example.com")

    await request_password_reset(db_session, email="creates-token@example.com")

    token_row = (await db_session.execute(
        select(PasswordResetToken).where(PasswordResetToken.user_id == auth["user_id"])
    )).scalar_one()
    assert token_row.used_at is None
    assert token_row.expires_at > datetime.now(timezone.utc)
    assert len(token_row.token_hash) == 64  # sha256 hex digest — never the raw token


async def test_reset_password_with_a_valid_token_updates_the_password(client: AsyncClient, db_session: AsyncSession):
    auth = await register_and_login(client, "reset-valid@example.com")
    raw_token, token_hash = generate_reset_token()
    db_session.add(PasswordResetToken(
        user_id=auth["user_id"], token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    ))
    await db_session.flush()

    ok = await reset_password(db_session, raw_token=raw_token, new_password="brandnewpassword123")
    assert ok is True

    old_login = await client.post("/api/v1/auth/login", json={"email": "reset-valid@example.com", "password": "testpass123"})
    assert old_login.status_code == 401
    new_login = await client.post("/api/v1/auth/login", json={"email": "reset-valid@example.com", "password": "brandnewpassword123"})
    assert new_login.status_code == 200


async def test_reset_password_token_cannot_be_reused(db_session: AsyncSession):
    user = User(email="no-reuse@example.com", hashed_password=hash_password("original12345"))
    db_session.add(user)
    await db_session.flush()

    raw_token, token_hash = generate_reset_token()
    db_session.add(PasswordResetToken(
        user_id=user.id, token_hash=token_hash, expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    ))
    await db_session.flush()

    first = await reset_password(db_session, raw_token=raw_token, new_password="firstnewpassword123")
    assert first is True

    second = await reset_password(db_session, raw_token=raw_token, new_password="secondnewpassword123")
    assert second is False


async def test_expired_reset_token_is_rejected(db_session: AsyncSession):
    user = User(email="expired-reset@example.com", hashed_password=hash_password("original12345"))
    db_session.add(user)
    await db_session.flush()

    raw_token, token_hash = generate_reset_token()
    db_session.add(PasswordResetToken(
        user_id=user.id, token_hash=token_hash, expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    ))
    await db_session.flush()

    ok = await reset_password(db_session, raw_token=raw_token, new_password="newpassword123")
    assert ok is False


async def test_reset_password_rejects_unknown_token(db_session: AsyncSession):
    ok = await reset_password(db_session, raw_token="totally-made-up-token", new_password="newpassword123")
    assert ok is False
