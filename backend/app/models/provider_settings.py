"""Per-organization AI provider configuration (BYOK).

One row per (org, kind) where kind is 'llm' or 'embedding'. The API key is
stored encrypted (see app.crypto); embedding_dim is captured for the embedding
row so the org's Qdrant collection is created with the right vector size.
"""
import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, UUIDPkMixin


class ProviderSettings(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "provider_settings"
    __table_args__ = (
        UniqueConstraint("org_id", "kind", name="uq_provider_settings_org_kind"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # llm | embedding
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)  # openai-compatible
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    # Non-reversible display hint (e.g. "••••1234") computed at write time, so
    # reads never decrypt the real key.
    api_key_hint: Mapped[str] = mapped_column(String(40), nullable=False, server_default="")
    embedding_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)  # embedding kind only
