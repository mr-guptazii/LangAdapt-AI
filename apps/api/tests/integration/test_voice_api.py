"""Regression coverage for a real production bug: /voice/transcribe used to
hard-depend on get_learner_profile, which 404s until onboarding completes —
but the placement assessment's speaking questions call this endpoint BEFORE
onboarding finishes, so every recording attempt during onboarding 404'd."""
from httpx import AsyncClient

from tests.integration.conftest import complete_onboarding, register_and_login


async def test_transcribe_works_before_onboarding_completes(client: AsyncClient):
    auth = await register_and_login(client, "preonboard-voice@example.com")
    token = auth["access_token"]

    resp = await client.post(
        "/api/v1/voice/transcribe",
        headers={"Authorization": f"Bearer {token}"},
        files={"audio": ("answer.webm", b"fake-audio-bytes", "audio/webm")},
        data={"target_language_code": "es"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_mock"] is True
    assert body["transcript"]


async def test_transcribe_uses_learner_profile_language_once_onboarded(client: AsyncClient):
    auth = await register_and_login(client, "postonboard-voice@example.com")
    token = auth["access_token"]
    await complete_onboarding(client, token)

    resp = await client.post(
        "/api/v1/voice/transcribe",
        headers={"Authorization": f"Bearer {token}"},
        files={"audio": ("answer.webm", b"fake-audio-bytes", "audio/webm")},
    )

    assert resp.status_code == 200, resp.text


async def test_transcribe_rejects_empty_audio(client: AsyncClient):
    auth = await register_and_login(client, "empty-audio-voice@example.com")
    token = auth["access_token"]

    resp = await client.post(
        "/api/v1/voice/transcribe",
        headers={"Authorization": f"Bearer {token}"},
        files={"audio": ("answer.webm", b"", "audio/webm")},
    )

    assert resp.status_code == 400
