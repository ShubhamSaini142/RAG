"""Qdrant implementation of VectorStore — one collection per organization.

Because each org brings its own embedding model (different vector dimensions),
a single shared collection won't work. Each org gets `org_<id>` sized to its
embedding dim. The org_id payload filter is kept as defense-in-depth.

Sync methods are used by the Celery ingestion worker; `asearch` uses an
AsyncQdrantClient for the request-serving retrieval path.
"""
import uuid

from qdrant_client import AsyncQdrantClient, QdrantClient, models

from app.config import settings
from app.vectorstore.base import Chunk, SearchHit, VectorStore

_async_client: AsyncQdrantClient | None = None


def org_collection(org_id: uuid.UUID | str) -> str:
    """Deterministic per-tenant collection name."""
    return f"org_{str(org_id).replace('-', '')}"


def _get_async_client() -> AsyncQdrantClient:
    global _async_client
    if _async_client is None:
        _async_client = AsyncQdrantClient(
            url=settings.qdrant_url, api_key=settings.qdrant_api_key or None
        )
    return _async_client


def _build_filter(org_id: str, collection_id: str | None) -> models.Filter:
    must = [models.FieldCondition(key="org_id", match=models.MatchValue(value=org_id))]
    if collection_id:
        must.append(
            models.FieldCondition(
                key="collection_id", match=models.MatchValue(value=collection_id)
            )
        )
    return models.Filter(must=must)


def _hits_from(result) -> list[SearchHit]:
    return [
        SearchHit(
            chunk_id=str(p.id),
            document_id=str((p.payload or {}).get("document_id")),
            content=(p.payload or {}).get("content", ""),
            score=p.score,
            metadata=p.payload or {},
        )
        for p in result.points
    ]


class QdrantStore(VectorStore):
    def __init__(self, collection: str) -> None:
        self.collection = collection
        self._client: QdrantClient | None = None

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(
                url=settings.qdrant_url, api_key=settings.qdrant_api_key or None
            )
        return self._client

    def ensure_collection(self, dim: int) -> None:
        if self.client.collection_exists(self.collection):
            # Fail loudly on a dimension mismatch rather than upserting wrong-sized
            # vectors into an existing collection.
            existing_dim = self.client.get_collection(self.collection).config.params.vectors.size
            if existing_dim != dim:
                raise ValueError(
                    f"Qdrant collection '{self.collection}' has dim {existing_dim}, "
                    f"but the configured embedding model produces dim {dim}. "
                    "Delete the org's documents to rebuild the index."
                )
            return
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
        )
        for field in ("org_id", "document_id", "collection_id"):
            self.client.create_payload_index(
                collection_name=self.collection,
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

    def upsert(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        points = [
            models.PointStruct(
                id=c.chunk_id,
                vector=c.embedding,
                payload={
                    "org_id": c.org_id,
                    "document_id": c.document_id,
                    "content": c.content,
                    **(c.metadata or {}),
                },
            )
            for c in chunks
        ]
        self.client.upsert(collection_name=self.collection, points=points)

    async def asearch(
        self,
        org_id: str,
        query_vector: list[float],
        top_k: int = 5,
        collection_id: str | None = None,
    ) -> list[SearchHit]:
        # The collection may not exist yet (org configured but nothing ingested).
        if not await _get_async_client().collection_exists(self.collection):
            return []
        result = await _get_async_client().query_points(
            collection_name=self.collection,
            query=query_vector,
            query_filter=_build_filter(org_id, collection_id),
            limit=top_k,
            with_payload=True,
        )
        return _hits_from(result)

    def delete_document(self, org_id: str, document_id: str) -> None:
        if not self.client.collection_exists(self.collection):
            return
        self.client.delete(
            collection_name=self.collection,
            points_selector=models.Filter(
                must=[
                    models.FieldCondition(key="org_id", match=models.MatchValue(value=org_id)),
                    models.FieldCondition(
                        key="document_id", match=models.MatchValue(value=document_id)
                    ),
                ]
            ),
        )

    def delete_collection(self) -> None:
        if self.client.collection_exists(self.collection):
            self.client.delete_collection(self.collection)
