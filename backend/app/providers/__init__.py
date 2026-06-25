"""Org-aware provider factories (BYOK).

Each organization configures its own LLM and embedding provider + key (stored
encrypted). These factories load that config, decrypt the key, and return a
ready provider. If the org hasn't configured one, they raise
ProviderNotConfigured (callers map this to HTTP 409).
"""
import uuid

from sqlalchemy.orm import Session

from app.providers.base import EmbeddingProvider, LLMProvider

__all__ = [
    "EmbeddingProvider",
    "LLMProvider",
    "ProviderNotConfigured",
    "get_llm_provider",
    "get_embedding_provider",
    "get_embedding_dim",
    "has_provider",
]


class ProviderNotConfigured(Exception):
    def __init__(self, kind: str) -> None:
        self.kind = kind
        super().__init__(f"No {kind} provider configured for this organization")


def _load(db: Session, org_id: uuid.UUID, kind: str):
    from app.models import ProviderSettings

    cfg = (
        db.query(ProviderSettings)
        .filter(ProviderSettings.org_id == org_id, ProviderSettings.kind == kind)
        .first()
    )
    if cfg is None:
        raise ProviderNotConfigured(kind)
    return cfg


def get_llm_provider(org_id: uuid.UUID, db: Session) -> LLMProvider:
    from app import crypto
    from app.providers import registry

    cfg = _load(db, org_id, "llm")
    return registry.build_llm(cfg.provider, cfg.model, crypto.decrypt(cfg.api_key_encrypted), cfg.base_url)


def get_embedding_provider(org_id: uuid.UUID, db: Session) -> EmbeddingProvider:
    from app import crypto
    from app.providers import registry

    cfg = _load(db, org_id, "embedding")
    return registry.build_embedding(
        cfg.provider, cfg.model, crypto.decrypt(cfg.api_key_encrypted), cfg.base_url
    )


def get_embedding_dim(org_id: uuid.UUID, db: Session) -> int:
    cfg = _load(db, org_id, "embedding")
    return cfg.embedding_dim or 0


def has_provider(db: Session, org_id: uuid.UUID, kind: str) -> bool:
    from app.models import ProviderSettings

    return (
        db.query(ProviderSettings)
        .filter(ProviderSettings.org_id == org_id, ProviderSettings.kind == kind)
        .first()
        is not None
    )
