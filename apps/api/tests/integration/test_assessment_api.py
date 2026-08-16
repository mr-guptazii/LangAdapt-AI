"""Regression coverage for a real production bug: assessment question
generation hardcoded target_language="the target language" (a literal
placeholder string, not the learner's actual choice), so the model picked a
language essentially at random. Reported live: an English-onboarding user
got a French vocabulary question. /assessment/start and /answer now accept
target_language_code and thread it into the prompt (assessment_service.py's
_language_name mapping)."""
from unittest.mock import patch

from httpx import AsyncClient

from tests.integration.conftest import register_and_login


async def test_start_assessment_passes_selected_language_to_prompt_builder(client: AsyncClient):
    auth = await register_and_login(client, "assess-lang@example.com")
    token = auth["access_token"]

    with patch(
        "app.services.assessment_service.build_assessment_question_prompt",
        return_value=[{"role": "system", "content": ""}, {"role": "user", "content": ""}],
    ) as mock_build:
        resp = await client.post(
            "/api/v1/assessment/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"target_language_code": "es"},
        )
        assert resp.status_code == 200, resp.text
        assert mock_build.call_args.kwargs["target_language"] == "Spanish"


async def test_start_assessment_defaults_to_english_without_a_language_code(client: AsyncClient):
    auth = await register_and_login(client, "assess-default-lang@example.com")
    token = auth["access_token"]

    with patch(
        "app.services.assessment_service.build_assessment_question_prompt",
        return_value=[{"role": "system", "content": ""}, {"role": "user", "content": ""}],
    ) as mock_build:
        resp = await client.post(
            "/api/v1/assessment/start",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert resp.status_code == 200, resp.text
        assert mock_build.call_args.kwargs["target_language"] == "English"


async def test_start_assessment_works_with_no_body_at_all(client: AsyncClient):
    auth = await register_and_login(client, "assess-nobody@example.com")
    token = auth["access_token"]

    resp = await client.post("/api/v1/assessment/start", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
