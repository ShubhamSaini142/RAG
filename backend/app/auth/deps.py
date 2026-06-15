"""Auth dependencies: resolve the current user, org, and role from the JWT.

Every protected endpoint depends on these, so tenant resolution and role
enforcement live in one place.
"""
import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.db import get_db
from app.models import Membership, User

bearer_scheme = HTTPBearer(auto_error=True)


def _unauthorized(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_access_token(creds.credentials)
    if not payload or not payload.get("sub"):
        raise _unauthorized()
    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except (ValueError, TypeError):
        raise _unauthorized()
    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized("User not found")
    return user


@dataclass
class CurrentContext:
    """The active request context: who, which org, what role."""

    user: User
    org_id: uuid.UUID
    role: str


def get_current_context(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentContext:
    payload = decode_access_token(creds.credentials)
    if not payload or not payload.get("sub") or not payload.get("org_id"):
        raise _unauthorized()
    try:
        user_id = uuid.UUID(str(payload["sub"]))
        org_id = uuid.UUID(str(payload["org_id"]))
    except (ValueError, TypeError):
        raise _unauthorized()
    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized("User not found")
    # The user must actually be a member of the org in the token.
    membership = (
        db.query(Membership)
        .filter(Membership.user_id == user_id, Membership.org_id == org_id)
        .first()
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )
    return CurrentContext(user=user, org_id=org_id, role=membership.role)


def require_role(*allowed: str):
    """Dependency factory: require the caller's role in their active org."""

    def checker(ctx: CurrentContext = Depends(get_current_context)) -> CurrentContext:
        if ctx.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {', '.join(allowed)}",
            )
        return ctx

    return checker
