from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class AdminDoctorCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


class AdminDoctorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime


class AdminDocumentRead(BaseModel):
    """Lightweight, read-only row for the admin's cross-doctor documents
    browse/search view -- not the full clinical record (that stays scoped to
    the owning doctor's own endpoints)."""

    id: UUID
    doctor_profile_id: UUID
    doctor_name: str
    doctor_email: str
    patient_name: str
    patient_email: str | None
    logo_url: str | None
    is_shared: bool
    fill_enabled: bool
    patient_submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime
