"""Registration, login, token refresh/rotation, logout, password reset."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthenticationError, ConflictError, ValidationError
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models import Invitation, Organization, PasswordResetToken, RefreshToken, User
from app.models.enums import Plan, Role
from app.schemas.auth import AcceptInvitationRequest, RegisterRequest, TokenResponse
from app.services import plans
from app.services.email import send_email

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def issue_tokens(db: Session, user: User) -> TokenResponse:
    raw_refresh = generate_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            expires_at=_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    db.commit()
    return TokenResponse(
        access_token=create_access_token(user.id, user.org_id, user.role),
        refresh_token=raw_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def register(db: Session, data: RegisterRequest) -> tuple[User, TokenResponse]:
    """Create a new organisation and its first admin in one transaction."""
    email = normalize_email(data.email)
    if db.scalar(select(User.id).where(User.email == email)):
        raise ConflictError("An account with this email already exists")

    org = Organization(name=data.organization_name.strip(), plan=Plan.FREE.value, members_count=1)
    db.add(org)
    db.flush()
    user = User(
        email=email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name.strip(),
        role=Role.ADMIN.value,
        org_id=org.id,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # concurrent signup with the same email
        db.rollback()
        raise ConflictError("An account with this email already exists")
    logger.info("Registered org_id=%s admin user_id=%s", org.id, user.id)
    return user, issue_tokens(db, user)


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        verify_password(password, DUMMY_PASSWORD_HASH)  # equalise timing
        raise AuthenticationError("Incorrect email or password")
    if not verify_password(password, user.hashed_password):
        raise AuthenticationError("Incorrect email or password")
    if not user.is_active:
        raise AuthenticationError("This account has been deactivated")
    return user


def refresh(db: Session, raw_refresh: str) -> TokenResponse:
    """Rotate: the old refresh token is revoked and a new pair is issued.

    If an already-revoked token is presented, it was probably stolen and used
    by someone else first — revoke every session for that user.
    """
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_refresh)))
    if token is None:
        raise AuthenticationError("Invalid refresh token")
    if token.revoked_at is not None:
        revoke_all_sessions(db, token.user_id)
        logger.warning("Refresh token reuse detected user_id=%s; all sessions revoked", token.user_id)
        raise AuthenticationError("Refresh token has been revoked")
    if token.expires_at <= _now():
        raise AuthenticationError("Refresh token expired")
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive")
    token.revoked_at = _now()
    return issue_tokens(db, user)


def logout(db: Session, raw_refresh: str) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(raw_refresh), RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    db.commit()


def revoke_all_sessions(db: Session, user_id) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    db.commit()


# --- Invitations -----------------------------------------------------------

def _valid_invitation(db: Session, raw_token: str) -> Invitation:
    inv = db.scalar(select(Invitation).where(Invitation.token_hash == hash_token(raw_token)))
    if inv is None or inv.accepted_at or inv.revoked_at or inv.expires_at <= _now():
        raise ValidationError("This invitation is invalid or has expired")
    return inv


def invitation_info(db: Session, raw_token: str) -> dict:
    inv = _valid_invitation(db, raw_token)
    org = db.get(Organization, inv.org_id)
    return {"email": inv.email, "organization_name": org.name, "role": inv.role}


def accept_invitation(db: Session, data: AcceptInvitationRequest) -> tuple[User, TokenResponse]:
    # Lock the invitation row so the same token can't be accepted twice concurrently.
    inv = _valid_invitation(db, data.token)
    inv = db.scalar(select(Invitation).where(Invitation.id == inv.id).with_for_update())
    if db.scalar(select(User.id).where(User.email == inv.email)):
        raise ConflictError("An account with this email already exists")
    org = db.get(Organization, inv.org_id)
    # Org and role come from the invitation the admin created — not from the request.
    user = User(
        email=inv.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name.strip(),
        role=inv.role,
        org_id=inv.org_id,
    )
    db.add(user)
    inv.accepted_at = _now()
    db.flush()
    plans.sync_members_count(db, org)
    db.commit()
    logger.info("Invitation accepted org_id=%s user_id=%s", org.id, user.id)
    return user, issue_tokens(db, user)


# --- Password reset ----------------------------------------------------------

def request_password_reset(db: Session, email: str) -> None:
    """Always behaves the same whether or not the email exists (no enumeration)."""
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or not user.is_active:
        return
    raw = generate_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=_now() + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES),
        )
    )
    db.commit()
    link = f"{settings.FRONTEND_URL}/reset-password?token={raw}"
    send_email(
        user.email,
        "Reset your KnowBot password",
        f"Hi {user.full_name},\n\nReset your password using this link "
        f"(valid for {settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes):\n{link}\n\n"
        "If you didn't request this, you can ignore this email.",
    )


def reset_password(db: Session, raw_token: str, new_password: str) -> None:
    token = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(raw_token)).with_for_update()
    )
    if token is None or token.used_at or token.expires_at <= _now():
        raise ValidationError("This reset link is invalid or has expired")
    user = db.get(User, token.user_id)
    user.hashed_password = hash_password(new_password)
    token.used_at = _now()
    db.commit()
    revoke_all_sessions(db, user.id)


def change_password(db: Session, user: User, current: str, new: str) -> None:
    if not verify_password(current, user.hashed_password):
        raise AuthenticationError("Current password is incorrect")
    user.hashed_password = hash_password(new)
    db.commit()
    revoke_all_sessions(db, user.id)
