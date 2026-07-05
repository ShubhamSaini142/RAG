"""Conversation history (chat sessions).

List the caller's conversations, open one with its full message history (assistant
messages carry resolved citations), or delete one. Everything is strictly scoped
to the caller's org AND user — you can only ever see your own conversations.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import CurrentContext, get_current_context
from app.db import get_db
from app.models import Chunk, Conversation, Document, Message
from app.models.enums import MessageRole

router = APIRouter(prefix="/conversations", tags=["chat"])


# ---- schemas ----
class ConversationSummary(BaseModel):
    id: str
    title: str | None = None
    created_at: str


class CitationOut(BaseModel):
    n: int
    chunk_id: str
    document_id: str
    document: str | None = None
    snippet: str


class MessageOut(BaseModel):
    role: str
    content: str
    citations: list[CitationOut] = []


class ConversationDetail(BaseModel):
    id: str
    title: str | None = None
    messages: list[MessageOut]


# ---- helpers ----
def _owned(db: Session, ctx: CurrentContext, conversation_id: uuid.UUID) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.org_id != ctx.org_id or conv.user_id != ctx.user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv


def _resolve_citations(db: Session, org_id: uuid.UUID, chunk_ids: list | None) -> list[CitationOut]:
    """Rebuild an assistant turn's citations from stored point ids -> chunk rows
    (+ the document filename), preserving the original order."""
    if not chunk_ids:
        return []
    point_ids: list[uuid.UUID] = []
    for cid in chunk_ids:
        try:
            point_ids.append(uuid.UUID(str(cid)))
        except (ValueError, TypeError):
            continue
    if not point_ids:
        return []

    chunks = (
        db.query(Chunk)
        .filter(Chunk.org_id == org_id, Chunk.qdrant_point_id.in_(point_ids))
        .all()
    )
    by_point = {str(c.qdrant_point_id): c for c in chunks}
    doc_ids = {c.document_id for c in chunks}
    names: dict[uuid.UUID, str | None] = {}
    if doc_ids:
        for d_id, fname in (
            db.query(Document.id, Document.filename).filter(Document.id.in_(doc_ids)).all()
        ):
            names[d_id] = fname

    citations: list[CitationOut] = []
    n = 0
    for cid in chunk_ids:
        c = by_point.get(str(cid))
        if c is None:
            continue
        n += 1
        citations.append(
            CitationOut(
                n=n,
                chunk_id=str(cid),
                document_id=str(c.document_id),
                document=names.get(c.document_id),
                snippet=(c.content or "")[:300],
            )
        )
    return citations


# ---- endpoints ----
@router.get("", response_model=list[ConversationSummary], summary="List your conversations")
def list_conversations(
    ctx: CurrentContext = Depends(get_current_context), db: Session = Depends(get_db)
) -> list[ConversationSummary]:
    rows = (
        db.query(Conversation)
        .filter(Conversation.org_id == ctx.org_id, Conversation.user_id == ctx.user.id)
        .order_by(Conversation.created_at.desc())
        .all()
    )
    return [
        ConversationSummary(id=str(c.id), title=c.title, created_at=c.created_at.isoformat())
        for c in rows
    ]


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetail,
    summary="Get a conversation with its messages (+ citations)",
)
def get_conversation(
    conversation_id: uuid.UUID,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ConversationDetail:
    conv = _owned(db, ctx, conversation_id)
    msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id, Message.org_id == ctx.org_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    messages = [
        MessageOut(
            role=m.role,
            content=m.content,
            citations=(
                _resolve_citations(db, ctx.org_id, m.cited_chunk_ids)
                if m.role == MessageRole.assistant.value
                else []
            ),
        )
        for m in msgs
    ]
    return ConversationDetail(id=str(conv.id), title=conv.title, messages=messages)


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation",
)
def delete_conversation(
    conversation_id: uuid.UUID,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> None:
    conv = _owned(db, ctx, conversation_id)
    db.delete(conv)  # messages cascade; usage_events.conversation_id -> NULL
    db.commit()
