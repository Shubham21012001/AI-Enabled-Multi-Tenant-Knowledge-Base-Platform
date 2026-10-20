import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_tenant_user, require_admin, require_super_admin
from app.models import User
from app.schemas.organization import (
    InvitationOut,
    InviteRequest,
    InviteResponse,
    MemberOut,
    OrganizationOut,
    OrganizationUpdate,
    PlanChangeRequest,
    RoleUpdate,
)
from app.services import org_service, plans

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("/me", response_model=OrganizationOut)
def my_org(user: User = Depends(get_tenant_user), db: Session = Depends(get_db)):
    return org_service.get_org(db, user.org_id)


@router.patch("/me", response_model=OrganizationOut)
def update_my_org(data: OrganizationUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return org_service.update_org(db, admin, data)


@router.get("/me/usage")
def my_usage(user: User = Depends(get_tenant_user), db: Session = Depends(get_db)):
    return plans.usage_summary(db, org_service.get_org(db, user.org_id))


@router.get("/plans")
def list_plans():
    return {
        name: {"members": l.members, "documents": l.documents, "questions_per_month": l.questions_per_month}
        for name, l in plans.PLAN_LIMITS.items()
    }


@router.put("/me/plan", response_model=OrganizationOut)
def change_plan(data: PlanChangeRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return org_service.change_plan(db, admin, data.plan)


# --- Members ---

@router.get("/me/members", response_model=list[MemberOut])
def list_members(user: User = Depends(get_tenant_user), db: Session = Depends(get_db)):
    return org_service.list_members(db, user)


@router.patch("/me/members/{member_id}", response_model=MemberOut)
def update_member_role(
    member_id: uuid.UUID, data: RoleUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    return org_service.update_role(db, admin, member_id, data.role)


@router.delete("/me/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(member_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    org_service.remove_member(db, admin, member_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Invitations ---

@router.post("/me/invitations", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
def invite(data: InviteRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    inv, url = org_service.invite(db, admin, data.email, data.role)
    return InviteResponse.model_validate({**InvitationOut.model_validate(inv).model_dump(), "invite_url": url})


@router.get("/me/invitations", response_model=list[InvitationOut])
def list_invitations(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return org_service.list_invitations(db, admin)


@router.delete("/me/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(invitation_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    org_service.revoke_invitation(db, admin, invitation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Platform (super admin) ---

admin_router = APIRouter(prefix="/admin", tags=["platform admin"])


@admin_router.get("/organizations", response_model=list[OrganizationOut])
def all_orgs(actor: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    return org_service.list_all_orgs(db, actor)


@admin_router.put("/organizations/{org_id}/plan", response_model=OrganizationOut)
def set_plan(
    org_id: uuid.UUID, data: PlanChangeRequest, actor: User = Depends(require_super_admin), db: Session = Depends(get_db)
):
    return org_service.set_org_plan(db, actor, org_id, data.plan)
