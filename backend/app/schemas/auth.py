import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _check_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
        raise ValueError("Password must contain letters and numbers")
    # bcrypt only uses the first 72 bytes; reject longer to avoid silent truncation.
    if len(v.encode()) > 72:
        raise ValueError("Password must be at most 72 bytes")
    return v


class RegisterRequest(BaseModel):
    """Self-service signup creates a NEW organisation with the caller as its admin.

    There is deliberately no `org_id` or `role` field: joining an existing
    organisation is only possible through an invitation from its admin.
    """

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str
    full_name: str = Field(min_length=1, max_length=200)
    organization_name: str = Field(min_length=2, max_length=200)

    _pw = field_validator("password")(_check_password)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AcceptInvitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=10, max_length=200)
    password: str
    full_name: str = Field(min_length=1, max_length=200)

    _pw = field_validator("password")(_check_password)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str

    _pw = field_validator("new_password")(_check_password)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str

    _pw = field_validator("new_password")(_check_password)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    org_id: uuid.UUID | None
    is_active: bool
    created_at: datetime


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=200)


class InvitationInfo(BaseModel):
    email: str
    organization_name: str
    role: str
