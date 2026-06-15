"""Qdrant implementation of VectorStore.

Tenant isolation: every search applies a payload filter on org_id. One shared
collection holds all tenants' vectors, separated by the org_id payload field
(indexed for fast filtering).
"""
from qdrant_client import QdrantClient, models

from app.config import settings
from app.vectorstore.base import Chunk, SearchHit, VectorStore


class QdrantStore(VectorStore):
    def __init__(self) -> None:
        self.collection = settings.qdrant_collection
        self._client: QdrantClient | None = None

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key or None,
            )
        return self._client

    def ensure_collection(self) -> None:
        if self.client.collection_exists(self.collection):
            return
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(
                size=settings.embedding_dim, distance=models.Distance.COSINE
            ),
        )
        # Index the payload fields we filter on (tenant isolation + scoping).
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

    def search(
        self,
        org_id: str,
        query_vector: list[float],
        top_k: int = 5,
        collection_id: str | None = None,
    ) -> list[SearchHit]:
        must = [models.FieldCondition(key="org_id", match=models.MatchValue(value=org_id))]
        if collection_id:
            must.append(
                models.FieldCondition(
                    key="collection_id", match=models.MatchValue(value=collection_id)
                )
            )
        result = self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            query_filter=models.Filter(must=must),
            limit=top_k,
            with_payload=True,
        )
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

    def delete_document(self, org_id: str, document_id: str) -> None:
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
