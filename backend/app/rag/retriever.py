"""Retrieval: embed the query and fetch top-k chunks from Qdrant, tenant-scoped."""
import uuid

from app import providers
from app.vectorstore.base import SearchHit
from app.vectorstore.qdrant_store import QdrantStore


def retrieve(
    org_id: uuid.UUID,
    query: str,
    top_k: int = 5,
    collection_id: uuid.UUID | None = None,
) -> list[SearchHit]:
    embedder = providers.get_embedding_provider()
    query_vector = embedder.embed_query(query)
    store = QdrantStore()
    return store.search(
        org_id=str(org_id),
        query_vector=query_vector,
        top_k=top_k,
        collection_id=str(collection_id) if collection_id else None,
    )
