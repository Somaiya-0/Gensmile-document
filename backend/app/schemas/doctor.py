import re
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.onboarding import ClinicRead, PatientProfileRead
from app.schemas.simulation import SmileSimulationRead

PHONE_PATTERN = re.compile(r"^[+\d().\-\s]{7,20}$")

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


from typing import Literal
from app.models.enums import DoctorPatientStatus

class DoctorPatientStatusUpdate(BaseModel):
    status: Literal["active", "inactive"]

class DoctorPatientRead(BaseModel):
    id: UUID
    patient_user_id: UUID
    full_name: str
    email: str | None
    phone: str | None
    gender: str | None
    birth_date: date | None
    status: DoctorPatientStatus
    linked_at: datetime
    last_visit: datetime | None


class DoctorPatientDetailRead(DoctorPatientRead):
    blood_group: str | None
    full_address: str | None
    preferred_contact_method: str
    recent_simulations: list[SmileSimulationRead]
    profile: PatientProfileRead | None
    total_consultations: int
    total_simulations: int


class DoctorProfileDetailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    full_name: str
    email: str
    specialty: str | None = None
    bio: str | None = None
    contact_phone: str | None = None
    affiliation: str | None = None
    license_number: str | None = None
    clinics: list[ClinicRead]
    created_at: datetime


class DoctorProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    email: str | None = Field(default=None, min_length=5, max_length=255)
    specialty: str | None = Field(default=None, max_length=255)
    bio: str | None = Field(default=None)
    contact_phone: str | None = Field(default=None, max_length=50)
    affiliation: str | None = Field(default=None, max_length=500)
    license_number: str | None = Field(default=None, max_length=100)
    clinic_name: str | None = Field(default=None, min_length=2, max_length=255)
    clinic_address: str | None = Field(default=None, min_length=5, max_length=1000)
    clinic_phone: str | None = Field(default=None, max_length=50)

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower()

    @field_validator("clinic_phone")
    @classmethod
    def validate_clinic_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not PHONE_PATTERN.match(normalized):
            raise ValueError("Clinic phone number format is invalid.")
        return normalized


class CreatePatientRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: str | None = Field(default=None, min_length=5, max_length=255)
    phone: str | None = Field(default=None, min_length=7, max_length=50)
    birth_date: date | None = None
    gender: str | None = Field(default=None, max_length=50)
    blood_group: str | None = Field(default=None, max_length=10)
    full_address: str | None = Field(default=None, min_length=5, max_length=1000)
    street_address: str | None = Field(default=None, min_length=2, max_length=255)
    city: str | None = Field(default=None, min_length=2, max_length=120)
    state_name: str | None = Field(default=None, min_length=2, max_length=120)
    state_code: str | None = Field(default=None, max_length=20)
    country_name: str | None = Field(default=None, min_length=2, max_length=120)
    country_code: str | None = Field(default=None, min_length=2, max_length=10)
    zip_code: str | None = Field(default=None, min_length=2, max_length=30)
    preferred_contact_method: str = "email"

    @field_validator(
        "email", "phone", "full_address", "street_address", "city",
        "state_name", "state_code", "country_name", "country_code", "zip_code",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not PHONE_PATTERN.match(normalized):
            raise ValueError("Phone number format is invalid.")
        return normalized

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("Birth date cannot be in the future.")
        return value

class UpdatePatientRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    email: str | None = Field(default=None, min_length=5, max_length=255)
    phone: str | None = Field(default=None, min_length=7, max_length=50)
    birth_date: date | None = None
    gender: str | None = Field(default=None, max_length=50)
    blood_group: str | None = Field(default=None, max_length=10)
    full_address: str | None = Field(default=None, min_length=5, max_length=1000)
    street_address: str | None = Field(default=None, min_length=2, max_length=255)
    city: str | None = Field(default=None, min_length=2, max_length=120)
    state_name: str | None = Field(default=None, min_length=2, max_length=120)
    state_code: str | None = Field(default=None, max_length=20)
    country_name: str | None = Field(default=None, min_length=2, max_length=120)
    country_code: str | None = Field(default=None, min_length=2, max_length=10)
    zip_code: str | None = Field(default=None, min_length=2, max_length=30)
    preferred_contact_method: str | None = Field(default=None, pattern="^(email|phone|sms)$")

    # Same as CreatePatientRequest.blank_to_none -- without this, saving the
    # edit form with e.g. Phone left blank sends "" and Pydantic rejects it
    # against min_length before the field ever reaches "leave it unset".
    @field_validator(
        "email", "phone", "full_address", "street_address", "city",
        "state_name", "state_code", "country_name", "country_code", "zip_code",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not PHONE_PATTERN.match(normalized):
            raise ValueError("Phone number format is invalid.")
        return normalized

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("Birth date cannot be in the future.")
        return value

class ClinicCreateRequest(BaseModel):
    clinic_name: str = Field(min_length=2, max_length=255)
    address: str = Field(min_length=5, max_length=1000)
    phone: str = Field(min_length=7, max_length=50)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        normalized = value.strip()
        if not PHONE_PATTERN.match(normalized):
            raise ValueError("Clinic phone number format is invalid.")
        return normalized


class ClinicUpdateRequest(BaseModel):
    clinic_name: str | None = Field(default=None, min_length=2, max_length=255)
    address: str | None = Field(default=None, min_length=5, max_length=1000)
    phone: str | None = Field(default=None, min_length=7, max_length=50)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not PHONE_PATTERN.match(normalized):
            raise ValueError("Clinic phone number format is invalid.")
        return normalized


class AvailabilityScheduleItem(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    slot_duration_minutes: int = Field(default=45, ge=15, le=240)
    is_active: bool = True


class AvailabilityScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    day_of_week: int
    day_name: str
    start_time: str
    end_time: str
    slot_duration_minutes: int
    is_active: bool


class AvailabilityUpdateRequest(BaseModel):
    schedules: list[AvailabilityScheduleItem] = Field(min_length=0, max_length=7)


class UnavailabilityCreateRequest(BaseModel):
    unavailable_date: date
    reason: str | None = Field(default=None, max_length=255)


# ── New: Clinic dashboard schemas ─────────────────────────────────────────────

class ClinicCreate(BaseModel):
    """Request body for creating a new clinic."""
    name: str = Field(min_length=2, max_length=255, description="Clinic display name")
    description: str | None = Field(default=None, max_length=1000)
    address: str = Field(min_length=5, max_length=1000)
    phone: str = Field(min_length=7, max_length=50)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        normalized = value.strip()
        if not PHONE_PATTERN.match(normalized):
            raise ValueError("Phone number format is invalid.")
        return normalized

    @field_validator("name", "address")
    @classmethod
    def strip_strings(cls, value: str) -> str:
        return value.strip()


class ClinicUpdate(BaseModel):
    """Request body for updating an existing clinic (all fields optional)."""
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    address: str | None = Field(default=None, min_length=5, max_length=1000)
    phone: str | None = Field(default=None, min_length=7, max_length=50)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not PHONE_PATTERN.match(normalized):
            raise ValueError("Phone number format is invalid.")
        return normalized


class ClinicResponse(BaseModel):
    """Standard clinic response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    doctor_profile_id: UUID
    clinic_name: str
    description: str | None = None
    address: str
    phone: str
    logo_name: str | None = None
    is_active: bool
    deactivation_reason: str | None = Field(
        default=None,
        description="Why is_active is False, if it is: 'manual', 'capacity_limit', or 'subscription_suspended'.",
    )
    sort_order: int
    created_at: datetime
    updated_at: datetime


class ClinicDetailResponse(ClinicResponse):
    """Extended clinic response with aggregate counts."""
    staff_count: int = Field(default=0, description="Number of active staff assigned")
    simulation_count: int = Field(default=0, description="Total simulations in this clinic")


class ClinicListResponse(BaseModel):
    """Paginated list of clinics."""
    items: list[ClinicResponse]
    total: int
    page: int
    page_size: int
    pages: int