"""Async ingestion pipeline (Celery).

Pipeline: load raw file -> extract -> chunk -> embed -> store (Qdrant vectors +
Postgres chunk rows) -> mark the document ready (or failed + error).

Idempotent & self-healing: each run first purges any vectors/rows from a prior
attempt and uses deterministic point ids, so retries overwrite rather than
duplicate. run_ingestion() is a plain function so it can be called synchronously
in tests; the Celery task is a thin wrapper.
"""
import asyncio
import logging
import uuid

from app import providers, storage
from app.celery_app import celery_app
from app.db import SessionLocal
from app.ingestion.chunking import chunk_text
from app.ingestion.extractors import extract
from app.models import Chunk, Document
from app.models.enums import DocumentStatus
from app.vectorstore.base import Chunk as VectorChunk
from app.vectorstore.qdrant_store import QdrantStore, org_collection

logger = logging.getLogger("app.ingestion")

# Fixed namespace -> point id is deterministic per (document, chunk_index), so a
# re-run overwrites the same points instead of creating duplicates.
_POINT_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00cf4fc964ff")


def run_ingestion(document_id: str) -> None:
    db = SessionLocal()
    doc_uuid = uuid.UUID(document_id)
    try:
        doc = db.get(Document, doc_uuid)
        if doc is None:
            return
        doc.status = DocumentStatus.processing.value
        db.commit()

        store = QdrantStore(org_collection(doc.org_id))
        try:
            # Resolve this org's embedding provider (BYOK). Raises if unconfigured.
            embedder = providers.get_embedding_provider(doc.org_id, db)
            dim = providers.get_embedding_dim(doc.org_id, db)
            store.ensure_collection(dim)
            # Self-healing: drop anything a previous attempt left behind.
            store.delete_document(str(doc.org_id), str(doc.id))
            db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
            db.commit()

            raw = storage.download_bytes(doc.storage_key)
            pieces: list[dict] = []
            for seg in extract(doc.source_type, raw):
                pieces.extend(chunk_text(seg["text"], seg.get("metadata")))

            if not pieces:
                doc.status = DocumentStatus.failed.value
                doc.error_msg = "No extractable text content"
                db.commit()
                return

            # Celery tasks are sync; drive the async embedder in a fresh loop.
            vectors = asyncio.run(embedder.embed_documents([p["content"] for p in pieces]))
            if len(vectors) != len(pieces):
                raise RuntimeError(
                    f"embedding count {len(vectors)} != chunk count {len(pieces)}"
                )

            vector_chunks: list[VectorChunk] = []
            for piece, vector in zip(pieces, vectors, strict=True):
                point_id = uuid.uuid5(_POINT_NAMESPACE, f"{doc.id}:{piece['chunk_index']}")
                db.add(
                    Chunk(
                        org_id=doc.org_id,
                        document_id=doc.id,
                        content=piece["content"],
                        chunk_index=piece["chunk_index"],
                        chunk_metadata=piece["metadata"],
                        qdrant_point_id=point_id,
                    )
                )
                vector_chunks.append(
                    VectorChunk(
                        chunk_id=str(point_id),
                        org_id=str(doc.org_id),
                        document_id=str(doc.id),
                        content=piece["content"],
                        embedding=vector,
                        metadata={
                            "collection_id": str(doc.collection_id) if doc.collection_id else None,
                            "chunk_index": piece["chunk_index"],
                            **(piece["metadata"] or {}),
                        },
                    )
                )

            # Upsert vectors first, then commit Postgres: a 'ready' document
            # therefore always has its vectors present. A crash between the two
            # leaves orphan vectors that the next run's purge cleans up.
            store.upsert(vector_chunks)
            doc.status = DocumentStatus.ready.value
            doc.error_msg = None
            db.commit()
        except Exception as exc:  # noqa: BLE001 - record failure on the document
            db.rollback()
            try:
                store.delete_document(str(doc.org_id), str(doc.id))
            except Exception:  # noqa: BLE001
                pass
            # Full detail goes to server logs only; the API-visible error_msg is a
            # sanitized category (provider exceptions can echo the BYOK key/base_url).
            logger.exception("ingestion failed for document %s", document_id)
            failed = db.get(Document, doc_uuid)
            if failed is not None:
                failed.status = DocumentStatus.failed.value
                failed.error_msg = f"Ingestion failed ({type(exc).__name__}). See server logs."
                db.commit()
            raise
    finally:
        db.close()


@celery_app.task(name="ingestion.process_document")
def process_document(document_id: str) -> None:
    run_ingestion(document_id)
