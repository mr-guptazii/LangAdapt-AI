from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration, sourced from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "LingoAdapt AI"
    ENV: Literal["development", "test", "production"] = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://lingoadapt:lingoadapt@localhost:5432/lingoadapt"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://lingoadapt:lingoadapt@localhost:5432/lingoadapt"
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

    # Voice providers
    STT_PROVIDER: Literal["mock", "openai_whisper"] = "mock"
    TTS_PROVIDER: Literal["mock", "openai_tts"] = "mock"
    PRONUNCIATION_PROVIDER: Literal["mock"] = "mock"
    STORE_RAW_AUDIO: bool = False

    # Embeddings (semantic memory)
    EMBEDDING_PROVIDER: Literal["anthropic", "mock"] = "mock"
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
