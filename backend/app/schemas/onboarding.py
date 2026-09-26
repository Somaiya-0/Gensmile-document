import re
from datetime import date, datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from app.models import ContactMethod, OnboardingStatus, OnboardingStep, PlanCode, UserRole

PHONE_PATTERN = re.compile(r"^[+\d().\-\s]{7,20}$")



def _normalize_text(value: str, *, label: str, min_length: int = 1) -> str:
    normalized_value = value.strip()
    if len(normalized_value) < min_length:
        raise ValueError(f"{label} is required.")
    return normalized_value


class OnboardingSessionCreate(BaseModel):
    role: UserRole


class AccountSetupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)
    accept_terms: bool
    referral_code: str | None = None
    sub_token: str | None = None

    @model_validator(mode="after")
    def validate_matching_passwords(self) -> "AccountSetupRequest":
        if self.password != self.confirm_password:
            raise ValueError("Password and confirm password must match.")
        if not self.accept_terms:
            raise ValueError("You must accept the terms to continue.")
        return self

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        return _normalize_text(value, label="Full name", min_length=2)


class PlanSelectionRequest(BaseModel):
    plan_code: PlanCode


class ClinicRequest(BaseModel):
    clinic_name: str = Field(min_length=2, max_length=255)
    address: str = Field(min_length=5, max_length=1000)
    phone: str = Field(min_length=7, max_length=50)
    logo_name: str | None = Field(default=None, max_length=255)

    @field_validator("clinic_name")
    @classmethod
    def validate_clinic_name(cls, value: str) -> str:
        return _normalize_text(value, label="Clinic name", min_length=2)

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str) -> str:
        return _normalize_text(value, label="Clinic address", min_length=5)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        normalized_value = _normalize_text(value, label="Clinic phone number", min_length=7)
        if not PHONE_PATTERN.match(normalized_value):
            raise ValueError("Clinic phone number format is invalid.")
        return normalized_value

    @field_validator("logo_name")
    @classmethod
    def validate_logo_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        return normalized_value or None


class StaffInviteRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    role: str = Field(min_length=2, max_length=100)

    @field_validator("full_name")
    @classmethod
    def validate_staff_name(cls, value: str) -> str:
        return _normalize_text(value, label="Staff name", min_length=2)

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        return _normalize_text(value, label="Staff role", min_length=2)


class DoctorDetailsRequest(BaseModel):
    clinics: list[ClinicRequest] = Field(min_length=1, max_length=10)
    staff_members: list[StaffInviteRequest] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_unique_staff_emails(self) -> "DoctorDetailsRequest":
        normalized_emails = [staff_member.email.lower() for staff_member in self.staff_members]
        if len(normalized_emails) != len(set(normalized_emails)):
            raise ValueError("Staff invite email addresses must be unique.")
        return self


class PatientDetailsRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=50)
    birth_date: date | None = None
    gender: str | None = Field(default=None, max_length=50)
    blood_group: str | None = Field(default=None, max_length=10)
    full_address: str = Field(min_length=5, max_length=1000)
    street_address: str = Field(min_length=2, max_length=255)
    city: str = Field(min_length=2, max_length=120)
    state_name: str = Field(min_length=2, max_length=120)
    state_code: str | None = Field(default=None, max_length=20)
    country_name: str = Field(min_length=2, max_length=120)
    country_code: str = Field(min_length=2, max_length=10)
    zip_code: str = Field(min_length=2, max_length=30)
    preferred_contact_method: ContactMethod

    @field_validator("full_name")
    @classmethod
    def validate_patient_name(cls, value: str) -> str:
        return _normalize_text(value, label="Full name", min_length=2)

    @field_validator("phone")
    @classmethod
    def validate_patient_phone(cls, value: str) -> str:
        normalized_value = _normalize_text(value, label="Phone number", min_length=7)
        if not PHONE_PATTERN.match(normalized_value):
            raise ValueError("Phone number format is invalid.")
        return normalized_value

    @field_validator(
        "full_address",
        "street_address",
        "city",
        "state_name",
        "country_name",
        "zip_code",
    )
    @classmethod
    def validate_required_text_fields(cls, value: str, info) -> str:
        label = info.field_name.replace("_", " ").title()
        min_length = 5 if info.field_name == "full_address" else 2
        return _normalize_text(value, label=label, min_length=min_length)

    @field_validator("country_code")
    @classmethod
    def validate_country_code(cls, value: str) -> str:
        normalized_value = value.strip().upper()
        if len(normalized_value) < 2:
            raise ValueError("Country code is required.")
        return normalized_value

    @field_validator("state_code")
    @classmethod
    def validate_state_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip().upper()
        return normalized_value or None

    @field_validator("gender", "blood_group")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("Birth date cannot be in the future.")
        return value


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: UserRole
    email: EmailStr
    full_name: str
    is_active: bool
    onboarding_completed: bool
    created_at: datetime
    updated_at: datetime


class ClinicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_name: str
    address: str
    phone: str
    logo_name: str | None
    sort_order: int

    @computed_field
    @property
    def logo_url(self) -> str | None:
        if not self.logo_name:
            return None
        try:
            from app.services.storage_service import generate_download_url
            return generate_download_url(self.logo_name)
        except Exception:
            return None


class StaffInviteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: EmailStr
    role: str
    sort_order: int


class DoctorProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinics: list[ClinicRead]
    staff_members: list[StaffInviteRead]


class PatientProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phone: str | None
    birth_date: date | None
    gender: str | None
    blood_group: str | None
    full_address: str | None
    street_address: str | None
    city: str | None
    state_name: str | None
    state_code: str | None
    country_name: str | None
    country_code: str | None
    zip_code: str | None
    preferred_contact_method: ContactMethod


class OnboardingSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: UserRole
    status: OnboardingStatus
    current_step: OnboardingStep
    selected_plan: PlanCode | None
    completed_at: date | None
    created_at: datetime
    updated_at: datetime
    user: AccountRead | None = None
    doctor_profile: DoctorProfileRead | None = None
    patient_profile: PatientProfileRead | None = None


class OnboardingPlanCatalog(BaseModel):
    code: PlanCode
    name: str
    monthly_price: int
    simulations_per_month: int
    description: str
    features: list[str]
    is_popular: bool


class OnboardingCompletionResponse(BaseModel):
    message: str
    session: OnboardingSessionRead
