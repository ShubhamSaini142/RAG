"""Document endpoints: upload, list, get, delete. All scoped to the caller's org."""
import hashlib
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app import providers, storage
from app.auth.deps import CurrentContext, get_current_context
from app.db import get_db
from app.ingestion.tasks import process_document
from app.models import Document
from app.models.enums import DocumentStatus, SourceType
from app.vectorstore.qdrant_store import QdrantStore, org_collection

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB cap (slice; raise/stream-to-S3 later)

# Slice scope: plain text only. Widen-coverage phase adds pdf/docx/excel/...
_EXT_TO_SOURCE = {
    "txt": SourceType.txt.value,
    "text": SourceType.txt.value,
    "md": SourceType.txt.value,
}


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    filename: str | None
    source_type: str
    status: str
    error_msg: str | None = None


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document (.txt / .md)",
)
def upload_document(
    file: UploadFile = File(...),
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    # Require-key: no embedding provider configured -> can't index, so reject early.
    if not providers.has_provider(db, ctx.org_id, "embedding"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Configure an embedding provider in Settings before uploading.",
        )

    name = file.filename or "upload.txt"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else "txt"
    source_type = _EXT_TO_SOURCE.get(ext)
    if source_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '.{ext}'. Supported: .txt, .md",
        )

    # Read with a hard cap so a huge upload can't OOM the API process.
    raw = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
        )
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    doc = Document(
        org_id=ctx.org_id,
        source_type=source_type,
        filename=name,
        content_hash=hashlib.sha256(raw).hexdigest(),
        status=DocumentStatus.queued.value,
        created_by=ctx.user.id,
    )
    db.add(doc)
    db.flush()  # assign doc.id

    doc.storage_key = f"{ctx.org_id}/{doc.id}/{name}"
    storage.upload_bytes(doc.storage_key, raw, content_type="text/plain")
    db.commit()
    db.refresh(doc)

    # Hand off to the async worker (extract -> chunk -> embed -> store).
    process_document.delay(str(doc.id))
    return DocumentResponse.model_validate(doc)


@router.get("", response_model=list[DocumentResponse], summary="List your documents")
def list_documents(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> list[DocumentResponse]:
    docs = (
        db.query(Document)
        .filter(Document.org_id == ctx.org_id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return [DocumentResponse.model_validate(d) for d in docs]


def _get_owned(document_id: uuid.UUID, ctx: CurrentContext, db: Session) -> Document:
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.org_id == ctx.org_id)
        .first()
    )
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


@router.get("/{document_id}", response_model=DocumentResponse, summary="Get a document (status)")
def get_document(
    document_id: uuid.UUID,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    return DocumentResponse.model_validate(_get_owned(document_id, ctx, db))


@router.delete(
    "/{document_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a document"
)
def delete_document(
    document_id: uuid.UUID,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> Response:
    doc = _get_owned(document_id, ctx, db)
    # Best-effort cleanup of external stores; DB cascade removes chunk rows.
    try:
        QdrantStore(org_collection(ctx.org_id)).delete_document(str(ctx.org_id), str(doc.id))
    except Exception:  # noqa: BLE001
        pass
    if doc.storage_key:
        try:
            storage.delete_object(doc.storage_key)
        except Exception:  # noqa: BLE001
            pass
    db.delete(doc)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
