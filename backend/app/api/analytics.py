"""Usage analytics endpoints.

`/analytics/me` returns the caller's own token usage; `/analytics/org` returns
the whole organization's usage and a per-user breakdown, restricted to
owners/admins. Both aggregate from the append-only `usage_events` table.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analytics.service import summary
from app.auth.deps import CurrentContext, get_current_context, require_role
from app.db import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/me", summary="Your own usage analytics")
def my_analytics(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    return summary(db, ctx.org_id, ctx.user.id)


@router.get("/org", summary="Organization-wide usage analytics (owner/admin)")
def org_analytics(
    ctx: CurrentContext = Depends(require_role("owner", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    return summary(db, ctx.org_id, None)
