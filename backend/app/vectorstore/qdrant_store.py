"""Qdrant implementation of VectorStore.

Tenant isolation: every search applies a payload filter on org_id.
Hybrid (dense + sparse) search is added in the RAG-query milestone.

NOTE: scaffold stub — method bodies land in the ingestion / query milestones.
"""
from app.config import settings
from app.vectorstore.base import Chunk, SearchHit, VectorStore


class QdrantStore(VectorStore):
    def __init__(self) -> None:
        self.collection = settings.qdrant_collection
        # Lazy client init so importing this module never needs a live Qdrant.
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from qdrant_client import QdrantClient

            self._client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key or None,
            )
        return self._client

    def ensure_collection(self) -> None:
        raise NotImplementedError("Implemented in the ingestion milestone.")

    def upsert(self, chunks: list[Chunk]) -> None:
        raise NotImplementedError("Implemented in the ingestion milestone.")

    def search(
        self, org_id: str, query_vector: list[float], top_k: int = 5,
        collection_id: str | None = None,
    ) -> list[SearchHit]:
        raise NotImplementedError("Implemented in the RAG-query milestone.")

    def delete_document(self, org_id: str, document_id: str) -> None:
        raise NotImplementedError("Implemented in the ingestion milestone.")
