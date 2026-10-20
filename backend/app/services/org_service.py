"""Organisation settings, plan changes, members and invitations.

Every function takes the acting admin (or user) and scopes by `actor.org_id`.
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.core.security import generate_token, hash_token
from app.models import Invitation, Organization, User
from app.models.enums import Role
from app.schemas.organization import OrganizationUpdate
from app.services import plans
from app.services.auth_service import normalize_email, revoke_all_sessions
from app.services.email import send_email


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_org(db: Session, org_id: uuid.UUID) -> Organization:
    org = db.get(Organization, org_id)
    if org is None:
        raise NotFoundError("Organization not found")
    return org


def update_org(db: Session, admin: User, data: OrganizationUpdate) -> Organization:
    org = get_org(db, admin.org_id)
    if data.name is not None:
        org.name = data.name.strip()
    if data.logo_url is not None:
        org.logo_url = str(data.logo_url)
    db.commit()
    return org


def change_plan(db: Session, admin: User, plan: str) -> Organization:
    """Demo plan switch. A real deployment would call a payment provider first."""
    org = get_org(db, admin.org_id)
    org.plan = plan
    db.commit()
    return org


# --- Members -----------------------------------------------------------------

def list_members(db: Session, actor: User) -> list[User]:
    return list(db.scalars(select(User).where(User.org_id == actor.org_id).order_by(User.created_at)))


def _get_member(db: Session, actor: User, member_id: uuid.UUID) -> User:
    member = db.scalar(select(User).where(User.id == member_id, User.org_id == actor.org_id))
    if member is None:
        # Same error whether the user doesn't exist or belongs to another org.
        raise NotFoundError("Member not found")
    return member


def _admin_count(db: Session, org_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count()).select_from(User).where(
            User.org_id == org_id, User.role == Role.ADMIN.value, User.is_active.is_(True)
        )
    ) or 0


def update_role(db: Session, admin: User, member_id: uuid.UUID, role: str) -> User:
    member = _get_member(db, admin, member_id)
    if member.role == Role.ADMIN.value and role != Role.ADMIN.value and _admin_count(db, admin.org_id) <= 1:
        raise ValidationError("An organization must keep at least one admin")
    member.role = role
    db.commit()
    revoke_all_sessions(db, member.id)  # their old JWT claims carry the old role
    return member


def remove_member(db: Session, admin: User, member_id: uuid.UUID) -> None:
    member = _get_member(db, admin, member_id)
    if member.id == admin.id:
        raise ValidationError("You can't remove yourself")
    if member.role == Role.ADMIN.value and _admin_count(db, admin.org_id) <= 1:
        raise ValidationError("An organization must keep at least one admin")
    db.delete(member)
    db.flush()
    plans.sync_members_count(db, get_org(db, admin.org_id))
    db.commit()


# --- Invitations -------------------------------------------------------------

def invite(db: Session, admin: User, email: str, role: str) -> tuple[Invitation, str]:
    org = get_org(db, admin.org_id)
    email = normalize_email(email)
    if db.scalar(select(User.id).where(User.email == email)):
        raise ConflictError("A user with this email already exists")
    existing = db.scalar(
        select(Invitation).where(
            Invitation.org_id == org.id,
            Invitation.email == email,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
            Invitation.expires_at > _now(),
        )
    )
    if existing:
        raise ConflictError("An active invitation already exists for this email")
    plans.ensure_can_add_member(db, org)

    raw = generate_token()
    inv = Invitation(
        org_id=org.id,
        email=email,
        role=role,
        token_hash=hash_token(raw),
        invited_by=admin.id,
        expires_at=_now() + timedelta(days=settings.INVITATION_EXPIRE_DAYS),
    )
    db.add(inv)
    db.commit()
    url = f"{settings.FRONTEND_URL}/accept-invite?token={raw}"
    send_email(
        email,
        f"You're invited to join {org.name} on KnowBot",
        f"{admin.full_name} invited you to join {org.name} on KnowBot as {role}.\n\n"
        f"Accept the invitation (valid for {settings.INVITATION_EXPIRE_DAYS} days):\n{url}",
    )
    return inv, url


def list_invitations(db: Session, admin: User) -> list[Invitation]:
    return list(
        db.scalars(
            select(Invitation)
            .where(
                Invitation.org_id == admin.org_id,
                Invitation.accepted_at.is_(None),
                Invitation.revoked_at.is_(None),
                Invitation.expires_at > _now(),
            )
            .order_by(Invitation.created_at.desc())
        )
    )


def revoke_invitation(db: Session, admin: User, invitation_id: uuid.UUID) -> None:
    inv = db.scalar(
        select(Invitation).where(Invitation.id == invitation_id, Invitation.org_id == admin.org_id)
    )
    if inv is None or inv.accepted_at or inv.revoked_at:
        raise NotFoundError("Invitation not found")
    inv.revoked_at = _now()
    db.commit()


# --- Super admin (platform level) ---------------------------------------------

def list_all_orgs(db: Session, actor: User) -> list[Organization]:
    if actor.role != Role.SUPER_ADMIN.value:
        raise PermissionDeniedError("Super admin role required")
    return list(db.scalars(select(Organization).order_by(Organization.created_at.desc())))


def set_org_plan(db: Session, actor: User, org_id: uuid.UUID, plan: str) -> Organization:
    if actor.role != Role.SUPER_ADMIN.value:
        raise PermissionDeniedError("Super admin role required")
    org = get_org(db, org_id)
    org.plan = plan
    db.commit()
    return org
