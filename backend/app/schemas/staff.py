from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import CreditTransactionType, StaffStatus
from app.models.staff import DEFAULT_PERMISSIONS

# Names that must never be accepted as a staff job title because they are
# plan names or system role identifiers that could confuse the UI or be
# exploited to display elevated-privilege labels.
_BLOCKED_ROLE_VALUES = {
    "professional",
    "custom",
    "starter",
    "growth",
    "free",
    "doctor",
    "patient",
    "superadmin",
    "super_admin",
    "super admin",
    "root",
}


def _validate_permissions(value: dict) -> dict:
    allowed_keys = set(DEFAULT_PERMISSIONS.keys())
    unknown = set(value.keys()) - allowed_keys
    if unknown:
        raise ValueError(f"Unknown permission keys: {', '.join(sorted(unknown))}")
    for key, val in value.items():
        if not isinstance(val, bool):
            raise ValueError(f"Permission '{key}' must be a boolean.")
    return {**DEFAULT_PERMISSIONS, **value}


class StaffCreateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    role: str = Field(min_length=2, max_length=100)
    permissions: dict = Field(default_factory=lambda: dict(DEFAULT_PERMISSIONS))
    primary_clinic_id: UUID | None = Field(
        default=None,
        description="Optionally assign this staff member to a clinic on creation",
    )

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("role")
    @classmethod
    def normalize_and_validate_role(cls, value: str) -> str:
        """Normalise and validate the staff job-title role.

        Only blocks plan names / system role identifiers (privilege-escalation
        risk). Any other freeform job title (e.g. "Office Manager") is kept
        as-is instead of being collapsed to the generic "other" -- that
        silently discarded the doctor's actual input and made every
        non-exact-match staff member show the same meaningless label.
        """
        stripped = value.strip()
        if stripped.lower() in _BLOCKED_ROLE_VALUES:
            raise ValueError(
                f"'{value}' is not a valid staff role. "
                f"It looks like a plan name or system role, not a job title."
            )
        return stripped

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: dict) -> dict:
        return _validate_permissions(value)


class StaffUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    role: str | None = Field(default=None, min_length=2, max_length=100)
    permissions: dict | None = None

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return value.strip() if value else None

    @field_validator("role")
    @classmethod
    def normalize_and_validate_role(cls, value: str | None) -> str | None:
        if not value:
            return None
        stripped = value.strip()
        if stripped.lower() in _BLOCKED_ROLE_VALUES:
            raise ValueError(
                f"'{value}' is not a valid staff role. "
                f"It looks like a plan name or system role, not a job title."
            )
        return stripped

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: dict | None) -> dict | None:
        if value is None:
            return None
        return _validate_permissions(value)


class StaffMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: str
    role: str
    status: StaffStatus
    permissions: dict
    is_active: bool
    deactivation_reason: str | None = Field(
        default=None,
        description="Why is_active is False, if it is: 'manual', 'capacity_limit', or 'subscription_suspended'.",
    )
    sort_order: int
    credit_balance: int = Field(default=0, description="Current simulation credit balance")
    primary_clinic_id: UUID | None = Field(
        default=None,
        description="Primary assigned clinic",
    )
    created_at: datetime
    updated_at: datetime
    setup_url: str | None = None


# ── Clinic assignment ─────────────────────────────────────────────────────────

class ClinicStaffAssignmentResponse(BaseModel):
    """Returned when a staff member is assigned to a clinic."""
    staff_id: UUID
    clinic_id: UUID
    assigned_at: datetime
    is_primary: bool = Field(
        default=True,
        description="Whether this is the staff member's primary clinic",
    )


# ── Credit management ─────────────────────────────────────────────────────────

class AdjustCreditRequest(BaseModel):
    """Request body for adjusting a staff member's credit balance."""
    credit_delta: int = Field(
        description="Amount to adjust (positive to add credits, negative to deduct)",
    )
    reason: str = Field(
        min_length=2,
        max_length=500,
        description="Human-readable reason for the adjustment",
    )
    transaction_type: CreditTransactionType = Field(
        default=CreditTransactionType.ADJUSTMENT,
        description="Type of credit transaction",
    )

    @field_validator("credit_delta")
    @classmethod
    def validate_delta(cls, value: int) -> int:
        if value == 0:
            raise ValueError("credit_delta must be non-zero.")
        return value


class CreditBalanceRead(BaseModel):
    """Staff member's credit balance, optionally scoped to a clinic."""
    staff_id: UUID
    credit_balance: int
    clinic_id: UUID | None = None
    clinic_name: str | None = None


class CreditTransactionRead(BaseModel):
    """A single credit transaction record."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    staff_member_id: UUID
    clinic_id: UUID | None
    simulation_id: UUID | None
    transaction_type: CreditTransactionType
    delta: int
    balance_after: int
    reason: str | None
    created_at: datetime


# ── Extended staff reads ──────────────────────────────────────────────────────

class StaffWithClinicsResponse(StaffMemberRead):
    """Staff member detail including assigned clinic info."""
    primary_clinic_name: str | None = Field(
        default=None,
        description="Name of the primary assigned clinic",
    )