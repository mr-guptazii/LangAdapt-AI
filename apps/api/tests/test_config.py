from app.core.config import _normalize_asyncpg_url


def test_normalizes_plain_postgres_scheme():
    assert _normalize_asyncpg_url("postgres://u:p@host/db") == "postgresql+asyncpg://u:p@host/db"


def test_normalizes_plain_postgresql_scheme():
    assert _normalize_asyncpg_url("postgresql://u:p@host/db") == "postgresql+asyncpg://u:p@host/db"


def test_leaves_already_correct_driver_untouched():
    assert _normalize_asyncpg_url("postgresql+asyncpg://u:p@host/db") == "postgresql+asyncpg://u:p@host/db"


def test_preserves_query_params():
    url = "postgres://u:p@host/db?sslmode=require"
    assert _normalize_asyncpg_url(url) == "postgresql+asyncpg://u:p@host/db?sslmode=require"
