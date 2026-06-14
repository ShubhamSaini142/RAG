"""Documents (uploaded files / websites) and their text chunks.

The chunk row is the system-of-record for management/joins; the actual
embedding vector lives in Qdrant, linked via qdrant_point_id.
"""
import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, UUIDPkMixin
from app.models.enums import DocumentStatus


class Document(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("collections.id", ondelete="SET NULL"), index=True, nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default=DocumentStatus.queued.value,
        server_default=DocumentStatus.queued.value,
        index=True,
    )
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    doc_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class Chunk(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "chunks"

    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    chunk_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    qdrant_point_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True, nullable=True)
