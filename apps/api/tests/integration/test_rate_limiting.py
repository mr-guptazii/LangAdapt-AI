"""Verifies the real Redis-backed rate limiter actually enforces its limit —
kept separate from the business-logic integration tests, which deliberately
bypass rate limiting (see conftest.py's _RATE_LIMIT_OVERRIDES) since httpx's
ASGITransport gives every virtual test user the same synthetic client IP."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.rate_limit import get_redis_client
from app.database.session import get_db
from app.main import app

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _clear_login_rate_limit_key():
    try:
        redis_client = get_redis_client()
        async for key in redis_client.scan_iter(match="ratelimit:auth_login:*"):
            await redis_client.delete(key)
    except Exception:
        pytest.skip("Redis not reachable — rate limiter test requires a real Redis instance")
    yield


async def test_login_is_rate_limited_after_repeated_failures(db_session):
    """Real limiter, real Redis, no dependency overrides for it — only get_db
    is swapped so this still uses the isolated test transaction."""
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            statuses = []
            for _ in range(12):
                resp = await client.post(
                    "/api/v1/auth/login", json={"email": "nobody@test.com", "password": "wrong"},
                )
                statuses.append(resp.status_code)
            assert 401 in statuses  # normal failed-login responses
            assert 429 in statuses  # and the limiter kicks in before request 12
            # once limited, it stays limited within the window
            assert statuses[-1] == 429
    finally:
        app.dependency_overrides.clear()
