"""Chat endpoint: retrieve tenant-scoped context, stream a grounded answer
with citations (Server-Sent Events), and persist the conversation.

DB work runs in a threadpool (the sessions are sync) so it never blocks the
event loop, and the turn is persisted in a finally block so a mid-stream client
disconnect still records what was produced.
"""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app import providers
from app.auth.deps import CurrentContext, get_current_context
from app.db import SessionLocal
from app.models import Collection, Conversation, Message
from app.models.enums import MessageRole
from app.providers import ProviderNotConfigured
from app.rag.pipeline import stream_answer
from app.rag.retriever import retrieve
from app.vectorstore.qdrant_store import org_collection

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    collection_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    top_k: int = Field(default=5, ge=1, le=20)


def _sse(event: str, data: dict | list) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _ensure_conversation(
    org_id: uuid.UUID, user_id: uuid.UUID, conversation_id: uuid.UUID | None, question: str
) -> str:
    """Reuse the caller's own conversation or start a new one; record the user turn."""
    db = SessionLocal()
    try:
        conv = None
        if conversation_id:
            existing = db.get(Conversation, conversation_id)
            # Must belong to this org AND this user (no same-org cross-user write).
            if existing is not None and existing.org_id == org_id and existing.user_id == user_id:
                conv = existing
        if conv is None:
            conv = Conversation(org_id=org_id, user_id=user_id, title=question[:80])
            db.add(conv)
            db.flush()
        db.add(
            Message(
                org_id=org_id,
                conversation_id=conv.id,
                role=MessageRole.user.value,
                content=question,
            )
        )
        conv_id = str(conv.id)
        db.commit()
        return conv_id
    finally:
        db.close()


def _persist_answer(
    org_id: uuid.UUID, conversation_id: str, answer: str, citation_ids: list[str]
) -> None:
    db = SessionLocal()
    try:
        db.add(
            Message(
                org_id=org_id,
                conversation_id=uuid.UUID(conversation_id),
                role=MessageRole.assistant.value,
                content=answer,
                cited_chunk_ids=citation_ids,
            )
        )
        db.commit()
    finally:
        db.close()


def _validate_collection(collection_id: uuid.UUID, org_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        coll = db.get(Collection, collection_id)
        if coll is None or coll.org_id != org_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    finally:
        db.close()


def _resolve_providers(org_id: uuid.UUID):
    """Load this org's embedding + LLM providers (BYOK). Raises ProviderNotConfigured."""
    db = SessionLocal()
    try:
        embedder = providers.get_embedding_provider(org_id, db)
        llm = providers.get_llm_provider(org_id, db)
        return embedder, llm
    finally:
        db.close()


@router.post(
    "",
    summary="Ask a question (streamed, cited answer)",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Server-Sent Events stream: a `citations` event, then "
            "`token` events with answer text, then a final `done` event.",
            "content": {"text/event-stream": {}},
        }
    },
)
async def chat(
    body: ChatRequest, ctx: CurrentContext = Depends(get_current_context)
) -> StreamingResponse:
    org_id = ctx.org_id
    user_id = ctx.user.id

    # Resolve the org's BYOK providers (require-key). 409 if not configured yet.
    try:
        embedder, llm = await run_in_threadpool(_resolve_providers, org_id)
    except ProviderNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"{exc}. Configure it in Settings."
        )

    # Defense-in-depth: a collection filter must belong to the caller's org.
    if body.collection_id:
        await run_in_threadpool(_validate_collection, body.collection_id, org_id)

    # Async retrieval over the org's own Qdrant collection.
    hits = await retrieve(
        org_id,
        body.question,
        embedder,
        org_collection(org_id),
        top_k=body.top_k,
        collection_id=body.collection_id,
    )
    citations = [
        {
            "n": i + 1,
            "chunk_id": h.chunk_id,
            "document_id": h.document_id,
            "snippet": h.content[:300],
            "score": h.score,
        }
        for i, h in enumerate(hits)
    ]

    async def event_stream():
        yield _sse("citations", citations)
        conv_id = await run_in_threadpool(
            _ensure_conversation, org_id, user_id, body.conversation_id, body.question
        )

        parts: list[str] = []
        persisted = False
        try:
            async for delta in stream_answer(body.question, hits, llm):
                parts.append(delta)
                yield _sse("token", {"text": delta})
        finally:
            # Persist even if the client disconnects mid-stream (records the
            # partial answer that was produced).
            if not persisted:
                persisted = True
                try:
                    await run_in_threadpool(
                        _persist_answer,
                        org_id,
                        conv_id,
                        "".join(parts),
                        [c["chunk_id"] for c in citations],
                    )
                except Exception:  # noqa: BLE001
                    pass

        yield _sse("done", {"conversation_id": conv_id})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
