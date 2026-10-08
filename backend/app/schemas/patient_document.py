from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PatientDocumentBase(BaseModel):
    patient_name: str = Field(min_length=1, max_length=255)
    patient_email: str | None = Field(default=None, max_length=255)
    patient_phone: str | None = Field(default=None, max_length=50)
    patient_user_id: UUID | None = None
    visit_date: datetime | None = None
    chief_concern: str | None = Field(default=None, max_length=2000)
    last_dds_visit: str | None = Field(default=None, max_length=255)
    cbct_taken: bool | None = None
    req_radiologist: str | None = Field(default=None, max_length=255)
    exam_salivary_ph: str | None = Field(default=None, max_length=50)
    recommend_salivary_test: bool | None = None
    cbct_notes: str | None = Field(default=None, max_length=2000)

    # Third molars
    third_molar_ll: str | None = Field(default=None, max_length=2000)
    third_molar_lr: str | None = Field(default=None, max_length=2000)
    third_molar_ul: str | None = Field(default=None, max_length=2000)
    third_molar_ur: str | None = Field(default=None, max_length=2000)
    cavitations: str | None = Field(default=None, max_length=2000)
    third_molar_recommendations: str | None = Field(default=None, max_length=2000)

    # Sinus areas
    sinus_ul: str | None = Field(default=None, max_length=2000)
    sinus_ur: str | None = Field(default=None, max_length=2000)
    existing_rcts: str | None = Field(default=None, max_length=2000)
    any_into_sinus: bool | None = None
    sinus_recommendations: str | None = Field(default=None, max_length=2000)

    # Periodontal
    periodontal_condition: str | None = Field(default=None, max_length=2000)
    tx_recommendations: str | None = Field(default=None, max_length=2000)
    md_referral: bool | None = None
    blood_test: bool | None = None

    # Occlusion
    occlusion: str | None = Field(default=None, max_length=2000)
    guidance: str | None = Field(default=None, max_length=2000)
    occlusion_recommendations: str | None = Field(default=None, max_length=2000)

    # Doctor-added fields from the Settings form-builder
    custom_fields: dict = Field(default_factory=dict)


class PatientDocumentCreate(PatientDocumentBase):
    # When patient_user_id is set, patient_name/email/phone are filled in
    # server-side from the linked patient record, so patient_name isn't
    # required from the client in that case.
    patient_name: str = Field(default="", max_length=255)
    # A one-off field layout for just this document (changed in the New
    # Document form's settings but not made permanent). Omitted = copy the
    # doctor's default.
    form_config: list[dict] | None = None


class PatientDocumentUpdate(BaseModel):
    patient_name: str | None = Field(default=None, min_length=1, max_length=255)
    patient_email: str | None = None
    patient_phone: str | None = None
    visit_date: datetime | None = None
    chief_concern: str | None = None
    last_dds_visit: str | None = None
    cbct_taken: bool | None = None
    req_radiologist: str | None = None
    exam_salivary_ph: str | None = None
    recommend_salivary_test: bool | None = None
    cbct_notes: str | None = None
    third_molar_ll: str | None = None
    third_molar_lr: str | None = None
    third_molar_ul: str | None = None
    third_molar_ur: str | None = None
    cavitations: str | None = None
    third_molar_recommendations: str | None = None
    sinus_ul: str | None = None
    sinus_ur: str | None = None
    existing_rcts: str | None = None
    any_into_sinus: bool | None = None
    sinus_recommendations: str | None = None
    periodontal_condition: str | None = None
    tx_recommendations: str | None = None
    md_referral: bool | None = None
    blood_test: bool | None = None
    occlusion: str | None = None
    guidance: str | None = None
    occlusion_recommendations: str | None = None
    custom_fields: dict | None = None
    is_active: bool | None = None
    fill_enabled: bool | None = None


class PatientDocumentFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_name: str
    file_type: str
    file_size: int
    file_url: str | None = None
    uploaded_by_patient: bool = False
    uploaded_by: UUID | None = None
    created_at: datetime


class PatientDocumentRead(PatientDocumentBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    doctor_profile_id: UUID
    is_active: bool
    logo_url: str | None = None
    form_config: list[dict] | None = None  # Document-specific form config

    # Doctor-to-doctor (files only)
    share_token: str
    is_shared: bool
    share_url: str | None = None

    # Patient self-fill
    fill_token: str
    fill_enabled: bool
    fill_url: str | None = None
    patient_submitted_at: datetime | None = None

    files: list[PatientDocumentFileRead] = []
    created_at: datetime
    updated_at: datetime


class PatientDocumentChangeLogRead(BaseModel):
    """One audit-trail entry: who changed what, from what value to what
    value. Shown on the doctor-to-doctor share page so every doctor who
    opens it sees who last touched the form and its settings."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    changed_by_name: str
    change_type: str  # "value" | "settings" | "file" | "sharing" | "document"
    field_key: str | None = None
    field_label: str
    old_value: str | None = None
    new_value: str | None = None
    created_at: datetime


class PatientDocumentPublicRead(BaseModel):
    """Doctor-to-doctor view: the same form fields/values and attached files
    the patient sees on their own self-fill link (PatientFillFormRead), plus
    the change history. Editable by any doctor/staff account that logs in --
    see the authenticated /doctor-to-doctor/documents/{share_token} routes.
    Kept as a separate schema from PatientDocumentRead so this route never
    accidentally exposes anything beyond what's rendered here (e.g. the
    document's own share_token/fill_token)."""

    model_config = ConfigDict(from_attributes=True)

    patient_name: str
    patient_email: str | None = None
    patient_phone: str | None = None
    doctor_name: str
    logo_url: str | None = None
    visit_date: datetime | None = None
    shared_at: datetime | None = None
    fields: list[dict] = []
    values: dict = {}
    files: list[PatientDocumentFileRead] = []
    changes: list[PatientDocumentChangeLogRead] = []


class PatientFillFormRead(BaseModel):
    """What the patient sees on the no-auth self-fill page."""

    id: UUID
    patient_name: str
    patient_email: str | None = None  # ADD THIS
    patient_phone: str | None = None  # ADD THIS
    visit_date: datetime | None = None
    doctor_name: str
    logo_url: str | None = None
    fields: list[dict]
    values: dict
    submitted: bool
    files: list[PatientDocumentFileRead] = []

class PatientFillFormSubmit(BaseModel):
    patient_name: str | None = Field(default=None, max_length=255)
    patient_email: str | None = Field(default=None, max_length=255)
    patient_phone: str | None = Field(default=None, max_length=50)
    visit_date: datetime | None = None
    values: dict = Field(default_factory=dict)


class LogoUploadResponse(BaseModel):
    logo_url: str


class DocumentFormConfigUpdate(BaseModel):
    """Update a document's specific form configuration."""
    fields: list[dict]

class SharedWithMeDocumentRead(BaseModel):
    """One row of a doctor's "Shared Documents" list: a document another
    doctor shared with them that they've opened through its link."""

    share_token: str
    patient_name: str
    owner_name: str
    logo_url: str | None = None
    visit_date: datetime | None = None
    updated_at: datetime
    last_opened_at: datetime
