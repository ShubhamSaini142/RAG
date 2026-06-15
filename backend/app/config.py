"""Application configuration, loaded from environment / .env."""
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Secrets that must never be used outside local development.
_INSECURE_SECRETS = {"change-me", "change-me-to-a-long-random-string"}

# .env lives in backend/ (config.py is at backend/app/config.py).
# Anchor to the backend dir so it loads no matter the working directory.
_BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_BACKEND_DIR / ".env", extra="ignore")

    # App
    app_env: str = "development"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60

    # Postgres
    postgres_user: str = "rag"
    postgres_password: str = "rag"
    postgres_db: str = "rag"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "kb_chunks"

    # Object storage
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "rag-documents"
    s3_region: str = "us-east-1"

    # OpenAI
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @model_validator(mode="after")
    def _require_strong_secret(self) -> "Settings":
        # Outside local dev, refuse to boot with a default/weak signing secret —
        # the JWT secret is the only thing preventing token forgery.
        if self.app_env != "development" and (
            self.secret_key in _INSECURE_SECRETS or len(self.secret_key) < 32
        ):
            raise ValueError(
                "SECRET_KEY must be a strong random value (>= 32 chars) when "
                "APP_ENV is not 'development'. Generate one with:\n"
                '  python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
