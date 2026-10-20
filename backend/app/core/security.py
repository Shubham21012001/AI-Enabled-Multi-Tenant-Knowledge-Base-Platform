"""Password hashing, JWTs and opaque token helpers."""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


# A real bcrypt hash used to keep login timing similar when the email doesn't
# exist (prevents user enumeration via response time).
DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing")


def create_access_token(user_id: uuid.UUID, org_id: uuid.UUID | None, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "org": str(org_id) if org_id else None,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != "access":
        return None
    return payload


def generate_token(nbytes: int = 32) -> str:
    """Random URL-safe token for refresh tokens, invitations and password resets."""
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """SHA-256 of a high-entropy random token.

    These tokens are random (not user-chosen passwords), so a fast hash is
    appropriate: brute-forcing 256 bits of randomness is infeasible, and a fast
    hash lets us look tokens up by their hash.
    """
    return hashlib.sha256(token.encode()).hexdigest()
