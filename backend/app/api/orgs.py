"""Organization endpoints: list, create, invite a member.

Invites target the caller's ACTIVE org (the org_id in their token), so a user
can only manage the org they're currently scoped to. Switching active org
means getting a token for that org (future endpoint).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import CurrentContext, get_current_user, require_role
from app.auth.schemas import CreateOrgRequest, InviteRequest, OrgResponse
from app.db import get_db
from app.models import Membership, Organization, User
from app.models.enums import Role

router = APIRouter(prefix="/orgs", tags=["orgs"])

# Privilege ranking — you may not grant a role higher than your own.
_ROLE_RANK = {Role.viewer.value: 0, Role.editor.value: 1, Role.admin.value: 2, Role.owner.value: 3}


@router.get("", response_model=list[OrgResponse])
def list_orgs(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[OrgResponse]:
    rows = (
        db.query(Organization, Membership)
        .join(Membership, Membership.org_id == Organization.id)
        .filter(Membership.user_id == user.id)
        .all()
    )
    return [OrgResponse(id=o.id, name=o.name, plan=o.plan, role=m.role) for o, m in rows]


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
def create_org(
    body: CreateOrgRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrgResponse:
    org = Organization(name=body.name)
    db.add(org)
    db.flush()
    db.add(Membership(user_id=user.id, org_id=org.id, role=Role.owner.value))
    db.commit()
    return OrgResponse(id=org.id, name=org.name, plan=org.plan, role=Role.owner.value)


@router.post("/invite", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
def invite_member(
    body: InviteRequest,
    ctx: CurrentContext = Depends(require_role(Role.owner.value, Role.admin.value)),
    db: Session = Depends(get_db),
) -> OrgResponse:
    # You cannot grant a role higher than your own (prevents an admin minting owners).
    if _ROLE_RANK[body.role.value] > _ROLE_RANK[ctx.role]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot grant a role higher than your own",
        )
    invitee = db.query(User).filter(User.email == body.email).first()
    if invitee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No user with that email — they must register first",
        )
    already = (
        db.query(Membership)
        .filter(Membership.user_id == invitee.id, Membership.org_id == ctx.org_id)
        .first()
    )
    if already:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User is already a member"
        )
    db.add(Membership(user_id=invitee.id, org_id=ctx.org_id, role=body.role.value))
    db.commit()
    org = db.get(Organization, ctx.org_id)
    return OrgResponse(id=org.id, name=org.name, plan=org.plan, role=body.role.value)
