from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        checks = [
            any(char.islower() for char in value),
            any(char.isupper() for char in value),
            any(char.isdigit() for char in value),
            any(not char.isalnum() for char in value),
        ]
        if sum(checks) < 3:
            raise ValueError(
                "Password must include at least three of: lowercase, uppercase, number, symbol"
            )
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    role: str | None = Field(default=None, max_length=80)
    organization: str | None = Field(default=None, max_length=255)
    language: str | None = Field(default=None, max_length=10)
    has_onboarded: bool | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str | None = None
    phone: str | None = None
    role: str | None = None
    organization: str | None = None
    language: str | None = "en"
    has_onboarded: bool | None = False
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthResponse(Token):
    refresh_token: str
    expires_in: int
    user: UserRead


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=32)


class OAuthCallback(BaseModel):
    code: str = Field(min_length=1)
    state: str | None = None


class FirebaseAuthRequest(BaseModel):
    id_token: str = Field(min_length=1)
