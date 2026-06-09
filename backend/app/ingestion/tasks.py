"""Celery tasks for async ingestion.

Pipeline: extract -> chunk -> embed -> store (Qdrant) -> mark document ready.

NOTE: scaffold stub — implemented in the ingestion milestone.
"""
from app.celery_app import celery_app


@celery_app.task(name="ingestion.process_document")
def process_document(document_id: str) -> None:
    """Run the full ingestion pipeline for one document.

    Steps:
      1. Load raw file from object storage / fetch URL
      2. Extract text (dispatch by source_type)
      3. Chunk (structure-aware) with source metadata
      4. Embed chunks (EmbeddingProvider)
      5. Upsert vectors + payload to Qdrant; write chunk rows to Postgres
      6. Update document.status = ready (or failed + error)
    """
    raise NotImplementedError("Implemented in the ingestion milestone.")
