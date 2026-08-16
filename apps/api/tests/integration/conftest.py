"""Integration test fixtures: a real Postgres connection wrapped in an outer
transaction that's rolled back after every test (SAVEPOINT-per-session, via
join_transaction_mode='create_savepoint') — full isolation without needing to
truncate tables between tests, and the app under test sees the exact same
committed-looking data its own db.commit() calls produce.

Requires a real Postgres reachable at TEST_DATABASE_URL (falls back to
DATABASE_URL, which is what CI sets against its disposable service container —
see .github/workflows/ci.yml). Locally, point TEST_DATABASE_URL at a
dedicated throwaway database so these tests never touch dev/demo data:
    TEST_DATABASE_URL=postgresql+asyncpg://lingoadapt:lingoadapt@127.0.0.1:5432/lingoadapt_test
Migrated once with: alembic upgrade b2c3d4e5f6a7 (the pgvector-independent
branch — see DATABASE.md's pgvector note for why that's the reachable head
on an environment without the extension).
"""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.auth import _forgot_password_limit, _login_limit, _register_limit, _reset_password_limit
from app.api.v1.chat import _chat_limit
from app.api.v1.practice import _generate_limit
from app.api.v1.voice import _synthesize_limit, _transcribe_limit
from app.core.config import settings
from app.database.session import get_db
from app.main import app

TEST_DB_URL = settings.TEST_DATABASE_URL or settings.DATABASE_URL

# Rate limiting (app/core/rate_limit.py) is real Redis-backed state, keyed by
# client IP for unauthenticated routes and (best-effort) by user id for
# authenticated ones. httpx's ASGITransport gives every virtual test user the
# same synthetic client IP, so without this override every test-created user
# would share ONE rate-limit bucket — that's a test-harness artifact, not the
# real production behavior, and it's not what these tests are checking (the
# rate limiter itself is verified directly in test_rate_limit.py). Overriding
# each limiter instance to a no-op is the standard FastAPI pattern for this.
_NOOP = lambda: None  # noqa: E731
_RATE_LIMIT_OVERRIDES = {
    _register_limit: _NOOP, _login_limit: _NOOP, _chat_limit: _NOOP,
    _generate_limit: _NOOP, _transcribe_limit: _NOOP, _synthesize_limit: _NOOP,
    _forgot_password_limit: _NOOP, _reset_password_limit: _NOOP,
}


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL)
    connection = await engine.connect()
    trans = await connection.begin()
    session_factory = async_sessionmaker(
        bind=connection, expire_on_commit=False, class_=AsyncSession, join_transaction_mode="create_savepoint"
    )
    session = session_factory()
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await connection.close()
        await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides.update(_RATE_LIMIT_OVERRIDES)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_skill(db_session: AsyncSession):
    """Minimal reference data most flows need: one 'en' language and the
    past_tense skill (the flagship demo skill exercised throughout).

    Looks up an existing row before inserting: TEST_DB_URL falls back to the
    real local dev DATABASE_URL when no dedicated test database is configured
    (see this file's module docstring), so if scripts/seed.py or manual local
    use has already committed an "en"/"past_tense" Skill row outside any test
    transaction, a blind unconditional insert here would leave two rows
    visible within this test's own transaction — every endpoint that queries
    Skill by (language_code, code) with .scalar_one_or_none() then raises
    MultipleResultsFound, which is what was actually happening (confirmed via
    a direct query against the dev DB: zero committed duplicates, but the
    fixture was adding a second one every run)."""
    from sqlalchemy import select

    from app.models.language import Skill

    existing = await db_session.execute(select(Skill).where(Skill.language_code == "en", Skill.code == "past_tense"))
    skill = existing.scalars().first()
    if skill is not None:
        return skill

    skill = Skill(
        language_code="en", code="past_tense", name="Past Tense", category="grammar",
        cefr_level="A2", description="Simple past for completed actions, including irregular verbs.",
    )
    db_session.add(skill)
    await db_session.flush()
    return skill


async def register_and_login(client: AsyncClient, email: str, password: str = "testpass123") -> dict:
    resp = await client.post("/api/v1/auth/register", json={"email": email, "password": password, "full_name": "Test User"})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def complete_onboarding(client: AsyncClient, token: str) -> dict:
    resp = await client.post(
        "/api/v1/onboarding/complete",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "native_language_code": "hi", "target_language_code": "en", "goal_types": ["career"],
            "self_estimated_level": "B1", "interests": ["technology"], "ai_personality": "encouraging", "correction_style": "balanced",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()
