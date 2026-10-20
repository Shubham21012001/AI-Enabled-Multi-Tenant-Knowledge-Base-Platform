"""Organisation API keys.

Format: kb_live_<random>. Only the SHA-256 hash and a short display prefix are
stored; the raw key is returned once, at creation time.
"""
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, NotFoundError, ValidationError
from app.core.security import hash_token
from app.models import ApiKey, User

KEY_PREFIX = "kb_live_"
MAX_ACTIVE_KEYS = 10


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create(db: Session, admin: User, name: str) -> tuple[ApiKey, str]:
    active = db.scalars(
        select(ApiKey.id).where(ApiKey.org_id == admin.org_id, ApiKey.revoked_at.is_(None))
    ).all()
    if len(active) >= MAX_ACTIVE_KEYS:
        raise ValidationError(f"An organization can have at most {MAX_ACTIVE_KEYS} active API keys")
    raw = KEY_PREFIX + secrets.token_urlsafe(32)
    key = ApiKey(
        org_id=admin.org_id,
        name=name.strip(),
        prefix=raw[: len(KEY_PREFIX) + 6],
        key_hash=hash_token(raw),
        created_by=admin.id,
    )
    db.add(key)
    db.commit()
    return key, raw


def list_keys(db: Session, admin: User) -> list[ApiKey]:
    return list(
        db.scalars(select(ApiKey).where(ApiKey.org_id == admin.org_id).order_by(ApiKey.created_at.desc()))
    )


def revoke(db: Session, admin: User, key_id: uuid.UUID) -> None:
    key = db.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.org_id == admin.org_id))
    if key is None:
        raise NotFoundError("API key not found")
    if key.revoked_at is None:
        key.revoked_at = _now()
        db.commit()


def authenticate(db: Session, raw_key: str) -> ApiKey:
    if not raw_key.startswith(KEY_PREFIX) or len(raw_key) > 100:
        raise AuthenticationError("Invalid API key")
    key = db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_token(raw_key)))
    if key is None or key.revoked_at is not None:
        raise AuthenticationError("Invalid or revoked API key")
    db.execute(
        update(ApiKey)
        .where(ApiKey.id == key.id)
        .values(usage_count=ApiKey.usage_count + 1, last_used_at=_now())
    )
    db.commit()
    return key
