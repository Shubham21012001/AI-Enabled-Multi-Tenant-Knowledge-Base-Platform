"""Request dependencies: authentication, roles and the tenant context.

Tenant isolation starts here: the org_id used by every service call comes from
the authenticated principal (JWT user or API key), never from request data.
"""
import uuid
from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token
from app.models import User
from app.models.enums import Role

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise AuthenticationError("Not authenticated")
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise AuthenticationError("Invalid or expired token")
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise AuthenticationError("Invalid token")
    user = db.get(User, user_id)
    # Re-checked on every request so deactivating a user takes effect within
    # one request, not after their token expires.
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive")
    return user


def get_tenant_user(user: User = Depends(get_current_user)) -> User:
    """A user who belongs to an organisation (i.e. not a platform-only super admin)."""
    if user.org_id is None:
        raise PermissionDeniedError("This action requires an organization account")
    return user


def require_admin(user: User = Depends(get_tenant_user)) -> User:
    if user.role != Role.ADMIN.value:
        raise PermissionDeniedError("Organization admin role required")
    return user


def require_super_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.SUPER_ADMIN.value:
        raise PermissionDeniedError("Super admin role required")
    return user


@dataclass(frozen=True)
class Principal:
    """Who is calling: a logged-in user, or an organisation API key."""

    org_id: uuid.UUID
    user: User | None = None
    api_key_id: uuid.UUID | None = None

    @property
    def user_id(self) -> uuid.UUID | None:
        return self.user.id if self.user else None

    @property
    def rate_limit_key(self) -> str:
        return f"user:{self.user_id}" if self.user else f"apikey:{self.api_key_id}"


def get_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Principal:
    """Accept either `Authorization: Bearer <jwt>` or `X-API-Key: kb_live_...`."""
    raw_key = request.headers.get("X-API-Key")
    if raw_key:
        from app.services import api_key_service

        api_key = api_key_service.authenticate(db, raw_key)
        return Principal(org_id=api_key.org_id, api_key_id=api_key.id)
    user = get_tenant_user(get_current_user(credentials, db))
    return Principal(org_id=user.org_id, user=user)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
