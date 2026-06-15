"""Auth endpoints: register, login, me."""
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.schemas import (
    LoginRequest,
    MeResponse,
    OrgResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.auth.security import create_access_token, hash_password, verify_password
from app.db import get_db
from app.models import Membership, Organization, User
from app.models.enums import Role

router = APIRouter(prefix="/auth", tags=["auth"])

# A throwaway hash verified on the "unknown email" path so login takes the same
# time whether or not the email exists (defeats timing-based user enumeration).
_DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=body.email, hashed_password=hash_password(body.password), name=body.name)
    db.add(user)
    db.flush()  # assign user.id

    # Clamp to the column limit (email can be up to 320 chars).
    org_name = (body.org_name or f"{body.name or body.email}'s Organization")[:255]
    org = Organization(name=org_name)
    db.add(org)
    db.flush()  # assign org.id

    db.add(Membership(user_id=user.id, org_id=org.id, role=Role.owner.value))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    token = create_access_token(user_id=user.id, org_id=org.id)
    return TokenResponse(access_token=token, org_id=org.id)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == body.email).first()
    # Always run bcrypt (against a dummy hash if no user) so response time
    # doesn't reveal whether the email is registered.
    hashed = user.hashed_password if user else _DUMMY_HASH
    if user is None or not verify_password(body.password, hashed):
        # Same message whether the email or password is wrong (don't leak which).
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    membership = (
        db.query(Membership)
        .filter(Membership.user_id == user.id)
        .order_by(Membership.created_at)
        .first()
    )
    org_id = membership.org_id if membership else None
    token = create_access_token(user_id=user.id, org_id=org_id)
    return TokenResponse(access_token=token, org_id=org_id)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MeResponse:
    rows = (
        db.query(Organization, Membership)
        .join(Membership, Membership.org_id == Organization.id)
        .filter(Membership.user_id == user.id)
        .all()
    )
    orgs = [OrgResponse(id=o.id, name=o.name, plan=o.plan, role=m.role) for o, m in rows]
    return MeResponse(user=UserResponse.model_validate(user), orgs=orgs)
