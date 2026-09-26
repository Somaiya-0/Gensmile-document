from enum import Enum


class DoctorPatientStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"


class UserRole(str, Enum):
    DOCTOR = "doctor"
    PATIENT = "patient"
    STAFF = "staff"
    ADMIN = "admin"
    AFFILIATE = "affiliate"  


class OnboardingStatus(str, Enum):
    STARTED = "started"
    ACCOUNT_SAVED = "account_saved"
    PLAN_SELECTED = "plan_selected"
    DETAILS_SAVED = "details_saved"
    COMPLETED = "completed"


class OnboardingStep(str, Enum):
    ACCOUNT = "account"
    PLAN = "plan"
    DETAILS = "details"
    COMPLETE = "complete"


class PlanCode(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class ContactMethod(str, Enum):
    SMS = "sms"
    EMAIL = "email"
    PHONE = "phone"


class SimulationStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in-review"
    ACCEPTED = "accepted"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class StaffStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"


class CreditTransactionType(str, Enum):
    INITIAL = "initial"
    PURCHASE = "purchase"
    SIMULATION_USAGE = "simulation_usage"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"
