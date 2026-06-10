"""Vector-store abstraction. Qdrant is the day-1 implementation; the
interface keeps per-tenant-collection / alternative stores swappable.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Chunk:
    chunk_id: str
    org_id: str
    document_id: str
    content: str
    embedding: list[float]
    metadata: dict


@dataclass
class SearchHit:
    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: dict


class VectorStore(ABC):
    @abstractmethod
    def ensure_collection(self) -> None:
        """Create the collection + payload indexes if absent."""

    @abstractmethod
    def upsert(self, chunks: list[Chunk]) -> None:
        """Insert/update chunk vectors with payload."""

    @abstractmethod
    def search(
        self, org_id: str, query_vector: list[float], top_k: int = 5,
        collection_id: str | None = None,
    ) -> list[SearchHit]:
        """Retrieve top-k chunks for a tenant (payload-filtered by org_id)."""

    @abstractmethod
    def delete_document(self, org_id: str, document_id: str) -> None:
        """Remove all vectors belonging to a document."""
