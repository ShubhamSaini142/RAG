"""Pydantic request/response models for auth & orgs."""
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import Role


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=255)
    org_name: str | None = Field(default=None, max_length=255)  # defaults to "<name>'s Organization"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    org_id: uuid.UUID | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    name: str | None = None


class OrgResponse(BaseModel):
    id: uuid.UUID
    name: str
    plan: str
    role: str  # the caller's role in this org


class CreateOrgRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class InviteRequest(BaseModel):
    email: EmailStr
    role: Role = Role.viewer


class MeResponse(BaseModel):
    user: UserResponse
    orgs: list[OrgResponse]
