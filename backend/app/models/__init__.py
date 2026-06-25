"""SQLAlchemy ORM models.

Importing this package registers every table on Base.metadata, which is
what Alembic autogenerate inspects. Every domain table carries org_id for
tenant isolation.
"""
from app.models.collection import Collection
from app.models.conversation import Conversation, Message
from app.models.document import Chunk, Document
from app.models.feedback import Feedback
from app.models.organization import Organization
from app.models.provider_settings import ProviderSettings
from app.models.user import Membership, User

__all__ = [
    "Organization",
    "User",
    "Membership",
    "Collection",
    "Document",
    "Chunk",
    "Conversation",
    "Message",
    "Feedback",
    "ProviderSettings",
]
