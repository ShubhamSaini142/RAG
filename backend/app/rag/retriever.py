"""Retrieval: hybrid (dense + sparse) search over Qdrant, tenant-scoped.

NOTE: scaffold stub — implemented in the RAG-query milestone.
"""
from app.vectorstore.base import SearchHit


def retrieve(
    org_id: str, query: str, top_k: int = 5, collection_id: str | None = None
) -> list[SearchHit]:
    """Embed the query and retrieve top-k chunks for the tenant."""
    raise NotImplementedError("Implemented in the RAG-query milestone.")
