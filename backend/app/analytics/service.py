"""Recording and aggregation for AI usage analytics.

`record_chat_usage` is called after each chat answer (best-effort, never blocks
the response). `summary` builds the numbers the dashboard renders — scoped to a
single user (their own view) or a whole org (owner/admin view).
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Conversation, Document, UsageEvent, User

logger = logging.getLogger("app.analytics")

WINDOW_DAYS = 30


def record_chat_usage(
    org_id: uuid.UUID,
    user_id: uuid.UUID | None,
    conversation_id: str | None,
    meta: tuple[str, str] | None,
    usage: dict | None,
) -> None:
    """Append one usage event for a completed chat answer. Best-effort:
    analytics must never break the chat path, so failures are swallowed."""
    provider, model = meta or ("unknown", "unknown")
    u = usage or {}
    inp = int(u.get("input_tokens") or 0)
    out = int(u.get("output_tokens") or 0)
    total = int(u.get("total_tokens") or 0) or (inp + out)

    db = SessionLocal()
    try:
        db.add(
            UsageEvent(
                org_id=org_id,
                user_id=user_id,
                conversation_id=uuid.UUID(conversation_id) if conversation_id else None,
                kind="chat",
                provider=provider,
                model=model,
                input_tokens=inp,
                output_tokens=out,
                total_tokens=total,
            )
        )
        db.commit()
    except Exception:  # noqa: BLE001 - analytics is non-critical
        db.rollback()
        logger.exception("failed to record usage event")
    finally:
        db.close()


def _scoped(query, org_id: uuid.UUID, user_id: uuid.UUID | None):
    query = query.filter(UsageEvent.org_id == org_id)
    if user_id is not None:
        query = query.filter(UsageEvent.user_id == user_id)
    return query


def summary(db: Session, org_id: uuid.UUID, user_id: uuid.UUID | None) -> dict:
    """Aggregate usage. Pass user_id for a personal view; None for org-wide."""
    scope = "org" if user_id is None else "me"

    # Totals across the whole history.
    t_input, t_output, t_total, requests = _scoped(
        db.query(
            func.coalesce(func.sum(UsageEvent.input_tokens), 0),
            func.coalesce(func.sum(UsageEvent.output_tokens), 0),
            func.coalesce(func.sum(UsageEvent.total_tokens), 0),
            func.count(UsageEvent.id),
        ),
        org_id,
        user_id,
    ).one()

    # Document + conversation counts (scoped the same way).
    docs_q = db.query(func.count(Document.id)).filter(Document.org_id == org_id)
    convs_q = db.query(func.count(Conversation.id)).filter(Conversation.org_id == org_id)
    if user_id is not None:
        docs_q = docs_q.filter(Document.created_by == user_id)
        convs_q = convs_q.filter(Conversation.user_id == user_id)

    # Daily time series over the trailing window.
    since = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    day = func.date_trunc("day", UsageEvent.created_at)
    daily_rows = (
        _scoped(
            db.query(
                day.label("day"),
                func.coalesce(func.sum(UsageEvent.input_tokens), 0),
                func.coalesce(func.sum(UsageEvent.output_tokens), 0),
                func.coalesce(func.sum(UsageEvent.total_tokens), 0),
                func.count(UsageEvent.id),
            ),
            org_id,
            user_id,
        )
        .filter(UsageEvent.created_at >= since)
        .group_by(day)
        .order_by(day)
        .all()
    )
    daily = [
        {
            "date": d.date().isoformat() if hasattr(d, "date") else str(d),
            "input_tokens": int(i),
            "output_tokens": int(o),
            "total_tokens": int(tot),
            "requests": int(r),
        }
        for d, i, o, tot, r in daily_rows
    ]

    # Breakdown by provider + model.
    model_rows = (
        _scoped(
            db.query(
                UsageEvent.provider,
                UsageEvent.model,
                func.coalesce(func.sum(UsageEvent.total_tokens), 0),
                func.count(UsageEvent.id),
            ),
            org_id,
            user_id,
        )
        .group_by(UsageEvent.provider, UsageEvent.model)
        .order_by(func.coalesce(func.sum(UsageEvent.total_tokens), 0).desc())
        .all()
    )
    by_model = [
        {"provider": p, "model": m, "total_tokens": int(tot), "requests": int(r)}
        for p, m, tot, r in model_rows
    ]

    result = {
        "scope": scope,
        "totals": {
            "input_tokens": int(t_input),
            "output_tokens": int(t_output),
            "total_tokens": int(t_total),
            "requests": int(requests),
            "documents": int(docs_q.scalar() or 0),
            "conversations": int(convs_q.scalar() or 0),
        },
        "daily": daily,
        "by_model": by_model,
    }

    # Org-wide view also breaks usage down per user.
    if user_id is None:
        user_rows = (
            db.query(
                UsageEvent.user_id,
                User.email,
                User.name,
                func.coalesce(func.sum(UsageEvent.total_tokens), 0),
                func.count(UsageEvent.id),
            )
            .outerjoin(User, User.id == UsageEvent.user_id)
            .filter(UsageEvent.org_id == org_id)
            .group_by(UsageEvent.user_id, User.email, User.name)
            .order_by(func.coalesce(func.sum(UsageEvent.total_tokens), 0).desc())
            .all()
        )
        result["by_user"] = [
            {
                "user_id": str(uid) if uid else None,
                "email": email or "(removed user)",
                "name": name,
                "total_tokens": int(tot),
                "requests": int(r),
            }
            for uid, email, name, tot, r in user_rows
        ]

    return result
