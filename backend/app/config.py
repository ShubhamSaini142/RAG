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
    encryption_key: str = ""  # Fernet key for encrypting per-org provider API keys

    # Postgres
    postgres_user: str = "rag"
    postgres_password: str = "rag"
    postgres_db: str = "rag"
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432

    # Redis
    redis_url: str = "redis://127.0.0.1:6379/0"

    # Qdrant
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "kb_chunks"

    # Object storage
    s3_endpoint_url: str = "http://127.0.0.1:9000"
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
        # Outside local dev, refuse to boot with weak/missing secrets rather than
        # failing lazily at request time.
        if self.app_env != "development":
            if self.secret_key in _INSECURE_SECRETS or len(self.secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY must be a strong random value (>= 32 chars) when "
                    "APP_ENV is not 'development'. Generate one with:\n"
                    '  python -c "import secrets; print(secrets.token_urlsafe(64))"'
                )
            if not self.encryption_key:
                raise ValueError(
                    "ENCRYPTION_KEY must be set when APP_ENV is not 'development'."
                )
            try:
                from cryptography.fernet import Fernet

                Fernet(self.encryption_key.encode())
            except Exception as exc:  # noqa: BLE001
                raise ValueError(
                    "ENCRYPTION_KEY must be a valid Fernet key. Generate one with:\n"
                    '  python -c "from cryptography.fernet import Fernet; '
                    'print(Fernet.generate_key().decode())"'
                ) from exc
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
