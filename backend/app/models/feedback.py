"""Thumbs up/down feedback on assistant messages."""
import uuid

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, UUIDPkMixin


class Feedback(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "feedback"

    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("messages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    rating: Mapped[str] = mapped_column(String(10), nullable=False)  # up / down
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
