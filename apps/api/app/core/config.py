from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_asyncpg_url(url: str) -> str:
    """Managed Postgres providers (Render, Railway, Heroku-style DATABASE_URL,
    etc.) hand out a plain postgres://... or postgresql://... connection
    string with no driver suffix — but SQLAlchemy's async engine requires
    postgresql+asyncpg://. Normalizing here means a platform's auto-provisioned
    DATABASE_URL can be wired in directly with no manual editing, instead of
    deployment silently breaking on a driver mismatch."""
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


class Settings(BaseSettings):
    """Central application configuration, sourced from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "LingoAdapt AI"
    ENV: Literal["development", "test", "production"] = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://lingoadapt:lingoadapt@localhost:5432/lingoadapt"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://lingoadapt:lingoadapt@localhost:5432/lingoadapt"

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def _fix_database_url_driver(cls, v: str) -> str:
        return _normalize_asyncpg_url(v)
    # Optional override so integration tests never touch the dev/demo database
    # locally; unset in CI, where DATABASE_URL already points at a disposable
    # per-run Postgres service container (see .github/workflows/ci.yml).
    TEST_DATABASE_URL: str | None = None

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    JWT_SECRET: str = "dev-insecure-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # LLM providers
    LLM_PROVIDER: Literal["anthropic", "openai", "mock"] = "mock"
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL_STRONG: str = "claude-sonnet-5"
    ANTHROPIC_MODEL_FAST: str = "claude-haiku-4-5-20251001"
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str | None = None
    OPENAI_MODEL_STRONG: str = "gpt-4o"
    OPENAI_MODEL_FAST: str = "gpt-4o-mini"

    # Voice providers. Model names are configurable (not hardcoded to OpenAI's
    # "whisper-1"/"tts-1") because openai_whisper/openai_tts hit whatever
    # OPENAI_BASE_URL points at (same OpenAI-Chat-Completions-style pattern as
    # the LLM provider) — e.g. Groq's OpenAI-compatible endpoint serves
    # "whisper-large-v3-turbo", not "whisper-1".
    STT_PROVIDER: Literal["mock", "openai_whisper"] = "mock"
    STT_MODEL: str = "whisper-1"
    TTS_PROVIDER: Literal["mock", "openai_tts"] = "mock"
    TTS_MODEL: str = "tts-1"
    PRONUNCIATION_PROVIDER: Literal["mock"] = "mock"
    STORE_RAW_AUDIO: bool = False

    # Embeddings (semantic memory). "hashing" is a real (not random) lightweight
    # lexical embedding — no API key needed, see ai/providers/lexical_provider.py
    # — and is the default so semantic memory retrieval is content-aware out of
    # the box. "mock" (pure random-per-text noise) is kept only for tests that
    # want speed/determinism without caring about actual similarity. No provider
    # named "anthropic" exists: Anthropic has no public embeddings API, and
    # nothing in this codebase ever implemented one despite the old default
    # suggesting otherwise.
    EMBEDDING_PROVIDER: Literal["hashing", "mock"] = "hashing"
    EMBEDDING_DIM: int = 384

    # Observability
    SENTRY_DSN: str | None = None
    LOG_LEVEL: str = "INFO"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # Frontend
    NEXT_PUBLIC_API_URL: str = "http://localhost:8000"

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
