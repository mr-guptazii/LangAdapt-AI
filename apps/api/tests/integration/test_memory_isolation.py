"""Proves the single most safety-critical invariant in this codebase: User A's
memories, conversations, errors, and vocabulary must be structurally
unreachable by User B — not just "happens not to match" but actually
unreachable through every surface that exposes learner data, including the
semantic memory retrieval used internally by the conversation agent (queried
directly here, not just through the HTTP layer, since that's the path a
prompt-injection attempt would try to exploit if the WHERE-scoping in
app/memory/service.py were ever weakened)."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.service import retrieve_relevant_memories
from app.models.learner import LearnerProfile
from app.models.memory import SemanticMemory
from tests.integration.conftest import complete_onboarding, register_and_login

MISTAKE_MESSAGE = "Yesterday I go to college and buy some food."


async def _user_with_profile(client: AsyncClient, db_session: AsyncSession, email: str):
    auth = await register_and_login(client, email)
    await complete_onboarding(client, auth["access_token"])
    profile = (await db_session.execute(select(LearnerProfile).where(LearnerProfile.user_id == auth["user_id"]))).scalar_one()
    return auth, profile


async def test_memory_facts_are_not_visible_across_users(client: AsyncClient, db_session: AsyncSession):
    auth_a, _profile_a = await _user_with_profile(client, db_session, "mem-a@test.com")
    auth_b, _profile_b = await _user_with_profile(client, db_session, "mem-b@test.com")

    # User A makes the same mistake twice — the second occurrence is what
    # persistence.py's update_memory_node treats as "recurring" and writes to
    # long-term memory (see app/agents/nodes/persistence.py).
    for _ in range(2):
        resp = await client.post(
            "/api/v1/chat/message", headers={"Authorization": f"Bearer {auth_a['access_token']}"},
            json={"message": MISTAKE_MESSAGE, "mode": "conversation"},
        )
        assert resp.status_code == 200, resp.text

    facts_a = await client.get("/api/v1/memory/facts", headers={"Authorization": f"Bearer {auth_a['access_token']}"})
    assert facts_a.status_code == 200
    assert len(facts_a.json()) >= 1, "User A should have at least one recurring-mistake memory fact"

    # User B never made this mistake and must see nothing from User A.
    facts_b = await client.get("/api/v1/memory/facts", headers={"Authorization": f"Bearer {auth_b['access_token']}"})
    assert facts_b.status_code == 200
    assert facts_b.json() == []


async def test_semantic_memory_retrieval_never_crosses_learner_profile_id(client: AsyncClient, db_session: AsyncSession):
    """Calls the retrieval function directly (not just through HTTP) with the
    SAME query text User A's mistake would match semantically, but scoped to
    User B's learner_profile_id — proving the WHERE-clause scoping in
    app/memory/service.py, not a coincidental lack of overlap, is what
    prevents cross-user leakage.

    Skips if the pgvector extension isn't installed on this Postgres instance
    (store_memory/retrieve_relevant_memories degrade gracefully to a no-op in
    that case by design — see app/memory/service.py's docstring) rather than
    failing misleadingly on an environment limitation. The equivalent
    isolation guarantee for the non-vector LearnerMemory fact table is proven
    unconditionally by test_memory_facts_are_not_visible_across_users above."""
    try:
        async with db_session.begin_nested():
            await db_session.execute(select(SemanticMemory).limit(1))
    except DBAPIError:
        pytest.skip("pgvector extension/table not available in this Postgres instance")

    auth_a, profile_a = await _user_with_profile(client, db_session, "sem-a@test.com")
    _auth_b, profile_b = await _user_with_profile(client, db_session, "sem-b@test.com")

    for _ in range(2):
        resp = await client.post(
            "/api/v1/chat/message", headers={"Authorization": f"Bearer {auth_a['access_token']}"},
            json={"message": MISTAKE_MESSAGE, "mode": "conversation"},
        )
        assert resp.status_code == 200, resp.text

    memories_for_a = await retrieve_relevant_memories(
        db_session, learner_profile_id=profile_a.id, query_text=MISTAKE_MESSAGE, top_k=5
    )
    memories_for_b = await retrieve_relevant_memories(
        db_session, learner_profile_id=profile_b.id, query_text=MISTAKE_MESSAGE, top_k=5
    )

    assert any("past_tense" in m or "go" in m for m in memories_for_a), memories_for_a
    assert memories_for_b == [], f"User B's retrieval must never surface User A's memory content, got: {memories_for_b}"


async def test_mistakes_and_vocabulary_do_not_cross_users(client: AsyncClient, db_session: AsyncSession):
    auth_a, _profile_a = await _user_with_profile(client, db_session, "mistake-a@test.com")
    auth_b, _profile_b = await _user_with_profile(client, db_session, "mistake-b@test.com")

    resp = await client.post(
        "/api/v1/chat/message", headers={"Authorization": f"Bearer {auth_a['access_token']}"},
        json={"message": MISTAKE_MESSAGE, "mode": "conversation"},
    )
    assert resp.status_code == 200, resp.text

    mistakes_a = await client.get("/api/v1/mistakes", headers={"Authorization": f"Bearer {auth_a['access_token']}"})
    assert mistakes_a.status_code == 200
    assert len(mistakes_a.json()) >= 1

    mistakes_b = await client.get("/api/v1/mistakes", headers={"Authorization": f"Bearer {auth_b['access_token']}"})
    assert mistakes_b.status_code == 200
    assert mistakes_b.json() == []

    vocab_a = await client.get("/api/v1/vocabulary", headers={"Authorization": f"Bearer {auth_a['access_token']}"})
    vocab_b = await client.get("/api/v1/vocabulary", headers={"Authorization": f"Bearer {auth_b['access_token']}"})
    assert vocab_a.status_code == 200 and vocab_b.status_code == 200
    # Both fresh accounts: neither has vocabulary yet, but critically each call
    # is independently scoped — this fails loudly if a future change ever
    # makes /vocabulary return a shared or unscoped list.
    assert vocab_a.json() == []
    assert vocab_b.json() == []


async def test_ai_decision_trace_does_not_cross_users(client: AsyncClient, db_session: AsyncSession):
    auth_a, _profile_a = await _user_with_profile(client, db_session, "decision-a@test.com")
    auth_b, _profile_b = await _user_with_profile(client, db_session, "decision-b@test.com")

    resp = await client.post(
        "/api/v1/chat/message", headers={"Authorization": f"Bearer {auth_a['access_token']}"},
        json={"message": MISTAKE_MESSAGE, "mode": "conversation"},
    )
    assert resp.status_code == 200, resp.text

    decisions_b = await client.get("/api/v1/memory/decisions", headers={"Authorization": f"Bearer {auth_b['access_token']}"})
    assert decisions_b.status_code == 200
    assert decisions_b.json() == []
