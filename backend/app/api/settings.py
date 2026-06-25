"""Per-org AI provider settings (BYOK).

GET is visible to any member (keys shown as a non-reversible hint — reads never
decrypt). PUT requires owner/admin. The embedding dimension is auto-detected by a
live probe (which also validates the key). Changing the embedding *dimension*
while documents exist is blocked, since the org's Qdrant collection is sized to
one dimension.

Provider validation errors are returned generically — provider/transport
exceptions can echo the submitted key or base_url, so they're never sent to the
client (full detail is logged server-side with the key redacted).
"""
import logging
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import crypto
from app.auth.deps import CurrentContext, get_current_context, require_role
from app.db import get_db
from app.models import Document, ProviderSettings
from app.models.enums import EmbeddingProviderName, LLMProviderName, ProviderKind, Role
from app.providers import registry
from app.vectorstore.qdrant_store import QdrantStore, org_collection

logger = logging.getLogger("app.api.settings")
router = APIRouter(prefix="/settings", tags=["settings"])


# ---- schemas ----
class ProviderConfigResponse(BaseModel):
    kind: str
    provider: str
    model: str
    base_url: str | None = None
    embedding_dim: int | None = None
    api_key_masked: str
    configured: bool = True


class ProvidersResponse(BaseModel):
    llm: ProviderConfigResponse | None = None
    embedding: ProviderConfigResponse | None = None


class SetLLMRequest(BaseModel):
    provider: LLMProviderName
    model: str
    api_key: str
    base_url: str | None = None


class SetEmbeddingRequest(BaseModel):
    provider: EmbeddingProviderName
    model: str
    api_key: str
    base_url: str | None = None


# ---- helpers ----
def _redact(text: str, secret: str) -> str:
    return text.replace(secret, "***") if secret else text


def _validate_base_url(url: str | None) -> None:
    if not url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="base_url is required for openai_compatible",
        )
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="base_url must be a valid http(s) URL",
        )


def _to_resp(cfg: ProviderSettings | None) -> ProviderConfigResponse | None:
    if cfg is None:
        return None
    return ProviderConfigResponse(
        kind=cfg.kind,
        provider=cfg.provider,
        model=cfg.model,
        base_url=cfg.base_url,
        embedding_dim=cfg.embedding_dim,
        api_key_masked=cfg.api_key_hint,  # precomputed hint — no decrypt on read
    )


def _get(db: Session, org_id: uuid.UUID, kind: str) -> ProviderSettings | None:
    return (
        db.query(ProviderSettings)
        .filter(ProviderSettings.org_id == org_id, ProviderSettings.kind == kind)
        .first()
    )


def _upsert(
    db: Session,
    org_id: uuid.UUID,
    kind: str,
    provider: str,
    model: str,
    api_key: str,
    base_url: str | None,
    embedding_dim: int | None = None,
) -> ProviderSettings:
    cfg = _get(db, org_id, kind)
    if cfg is None:
        cfg = ProviderSettings(org_id=org_id, kind=kind)
        db.add(cfg)
    cfg.provider = provider
    cfg.model = model
    cfg.api_key_encrypted = crypto.encrypt(api_key)
    cfg.api_key_hint = crypto.mask(api_key)
    cfg.base_url = base_url
    cfg.embedding_dim = embedding_dim
    db.commit()
    db.refresh(cfg)
    return cfg


# ---- endpoints ----
@router.get("/providers", response_model=ProvidersResponse, summary="Get this org's provider config")
def get_providers(
    ctx: CurrentContext = Depends(get_current_context), db: Session = Depends(get_db)
) -> ProvidersResponse:
    return ProvidersResponse(
        llm=_to_resp(_get(db, ctx.org_id, ProviderKind.llm.value)),
        embedding=_to_resp(_get(db, ctx.org_id, ProviderKind.embedding.value)),
    )


@router.put(
    "/providers/llm",
    response_model=ProviderConfigResponse,
    summary="Set the LLM provider + key (owner/admin)",
)
def set_llm(
    body: SetLLMRequest,
    ctx: CurrentContext = Depends(require_role(Role.owner.value, Role.admin.value)),
    db: Session = Depends(get_db),
) -> ProviderConfigResponse:
    if body.provider == LLMProviderName.openai_compatible:
        _validate_base_url(body.base_url)
    try:
        registry.build_llm(body.provider.value, body.model, body.api_key, body.base_url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM provider validation failed: %s", _redact(str(exc), body.api_key))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid LLM provider configuration or API key",
        )
    cfg = _upsert(
        db, ctx.org_id, ProviderKind.llm.value, body.provider.value, body.model, body.api_key, body.base_url
    )
    return _to_resp(cfg)


@router.put(
    "/providers/embedding",
    response_model=ProviderConfigResponse,
    summary="Set the embedding provider + key (owner/admin)",
)
async def set_embedding(
    body: SetEmbeddingRequest,
    ctx: CurrentContext = Depends(require_role(Role.owner.value, Role.admin.value)),
    db: Session = Depends(get_db),
) -> ProviderConfigResponse:
    if body.provider == EmbeddingProviderName.openai_compatible:
        _validate_base_url(body.base_url)

    # Live probe: validates the key AND auto-detects the vector dimension.
    try:
        emb = registry.build_embedding(body.provider.value, body.model, body.api_key, body.base_url)
        dim = len(await emb.embed_query("dimension probe"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("embedding provider validation failed: %s", _redact(str(exc), body.api_key))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not validate embedding provider or API key",
        )

    # Guard on the actual vector DIMENSION (not provider/model strings): a dim
    # change is what breaks the org's fixed-size Qdrant collection.
    existing = _get(db, ctx.org_id, ProviderKind.embedding.value)
    dim_changed = existing is not None and existing.embedding_dim != dim
    if dim_changed:
        doc_count = db.query(Document).filter(Document.org_id == ctx.org_id).count()
        if doc_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Delete existing documents before changing the embedding model "
                "(its vector dimension differs — the index must be rebuilt).",
            )
        # No documents: drop the stale collection deterministically so it's
        # recreated at the new dimension on next ingest. Fail (don't swallow).
        try:
            QdrantStore(org_collection(ctx.org_id)).delete_collection()
        except Exception:  # noqa: BLE001
            logger.exception("failed to drop stale collection for org %s", ctx.org_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not reset the vector index; try again.",
            )

    cfg = _upsert(
        db,
        ctx.org_id,
        ProviderKind.embedding.value,
        body.provider.value,
        body.model,
        body.api_key,
        body.base_url,
        embedding_dim=dim,
    )
    return _to_resp(cfg)
