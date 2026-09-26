import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.schemas.onboarding import AccountRead, DoctorProfileRead, PatientProfileRead


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.lower().strip()


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)

    @field_validator("refresh_token")
    @classmethod
    def validate_refresh_token(cls, value: str) -> str:
        return value.strip()


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)

    @field_validator("refresh_token")
    @classmethod
    def validate_refresh_token(cls, value: str) -> str:
        return value.strip()


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime
    user: AccountRead


class LogoutResponse(BaseModel):
    message: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.lower().strip()


class ForgotPasswordResponse(BaseModel):
    message: str
    reset_token: str | None = None
    reset_url: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512)
    password: str = Field(min_length=1, max_length=128)
    confirm_password: str = Field(min_length=1, max_length=128)

    @field_validator("token")
    @classmethod
    def validate_token(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_passwords(self) -> "ResetPasswordRequest":
        if self.password != self.confirm_password:
            raise ValueError("Password and confirm password must match.")
        return self


class ResetPasswordResponse(BaseModel):
    message: str


class CurrentUserResponse(BaseModel):
    user: AccountRead
    doctor_profile: DoctorProfileRead | None = None
    patient_profile: PatientProfileRead | None = None


class AccessTokenPayload(BaseModel):
    sub: UUID
    email: str
    role: str
    type: str
    exp: int | None = None
    iat: int | None = None