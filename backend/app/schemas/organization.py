import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    plan: str
    members_count: int
    docs_count: int
    logo_url: str | None
    created_at: datetime


class OrganizationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=200)
    logo_url: HttpUrl | None = None


class PlanChangeRequest(BaseModel):
    plan: Literal["free", "pro", "enterprise"]


class InviteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    role: Literal["admin", "member"] = "member"


class InvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str
    expires_at: datetime
    created_at: datetime


class InviteResponse(InvitationOut):
    # Returned once so an admin can share the link manually when email isn't configured.
    invite_url: str


class RoleUpdate(BaseModel):
    role: Literal["admin", "member"]


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
