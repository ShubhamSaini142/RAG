"""Retrieval: embed the query (async) and fetch top-k chunks from the org's
Qdrant collection. The embedding provider + collection are resolved by the
caller (which holds the DB session) and passed in.
"""
import uuid

from app.providers.base import EmbeddingProvider
from app.vectorstore.base import SearchHit
from app.vectorstore.qdrant_store import QdrantStore


async def retrieve(
    org_id: uuid.UUID,
    query: str,
    embedder: EmbeddingProvider,
    collection: str,
    top_k: int = 5,
    collection_id: uuid.UUID | None = None,
) -> list[SearchHit]:
    query_vector = await embedder.embed_query(query)
    store = QdrantStore(collection)
    return await store.asearch(
        org_id=str(org_id),
        query_vector=query_vector,
        top_k=top_k,
        collection_id=str(collection_id) if collection_id else None,
    )
