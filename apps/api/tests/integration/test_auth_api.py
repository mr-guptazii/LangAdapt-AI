import pytest
from httpx import AsyncClient

from tests.integration.conftest import register_and_login

pytestmark = pytest.mark.asyncio


async def test_register_creates_user_and_returns_token(client: AsyncClient):
    data = await register_and_login(client, "newuser@test.com")
    assert data["access_token"]
    assert data["onboarding_completed"] is False


async def test_register_duplicate_email_returns_409(client: AsyncClient):
    await register_and_login(client, "dupe@test.com")
    resp = await client.post("/api/v1/auth/register", json={"email": "dupe@test.com", "password": "testpass123"})
    assert resp.status_code == 409
    body = resp.json()
    assert body["success"] is False
    assert "error" in body


async def test_login_wrong_password_returns_401(client: AsyncClient):
    await register_and_login(client, "wrongpw@test.com")
    resp = await client.post("/api/v1/auth/login", json={"email": "wrongpw@test.com", "password": "not-the-password"})
    assert resp.status_code == 401


async def test_login_success_returns_token(client: AsyncClient):
    await register_and_login(client, "loginok@test.com", password="correcthorse123")
    resp = await client.post("/api/v1/auth/login", json={"email": "loginok@test.com", "password": "correcthorse123"})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


async def test_me_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_returns_current_user(client: AsyncClient):
    data = await register_and_login(client, "whoami@test.com")
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "whoami@test.com"
    assert body["is_admin"] is False


async def test_password_too_short_is_rejected(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={"email": "short@test.com", "password": "short"})
    assert resp.status_code == 422
