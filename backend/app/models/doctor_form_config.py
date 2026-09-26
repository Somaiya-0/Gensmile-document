from uuid import UUID

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# Default field layout, seeded the first time a doctor opens Settings.
# `core=True` fields map 1:1 to fixed columns on PatientDocument -- a doctor
# can hide/relabel/reorder/toggle patient-editable on them, but not delete
# them outright (deleting would orphan data). Anything the doctor adds
# beyond this list gets core=False and is stored in
# PatientDocument.custom_fields instead of a new DB column.
DEFAULT_FORM_FIELDS = [
    {"key": "chief_concern", "label": "Chief Concern", "type": "textarea", "section": "Overview", "order": 1, "active": True, "required": False, "patient_editable": True, "core": True},
    {"key": "last_dds_visit", "label": "Last DDS Visit", "type": "text", "section": "CBCT Information", "order": 2, "active": True, "required": False, "patient_editable": True, "core": True},
    {"key": "cbct_taken", "label": "CBCT Taken", "type": "checkbox", "section": "CBCT Information", "order": 3, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "req_radiologist", "label": "Requesting Radiologist", "type": "text", "section": "CBCT Information", "order": 4, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "exam_salivary_ph", "label": "Salivary pH", "type": "text", "section": "CBCT Information", "order": 5, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "recommend_salivary_test", "label": "Recommend Salivary Test", "type": "checkbox", "section": "CBCT Information", "order": 6, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "cbct_notes", "label": "CBCT Notes", "type": "textarea", "section": "CBCT Information", "order": 7, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "third_molar_ll", "label": "LL", "type": "textarea", "section": "Third Molars", "order": 8, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "third_molar_lr", "label": "LR", "type": "textarea", "section": "Third Molars", "order": 9, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "third_molar_ul", "label": "UL", "type": "textarea", "section": "Third Molars", "order": 10, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "third_molar_ur", "label": "UR", "type": "textarea", "section": "Third Molars", "order": 11, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "cavitations", "label": "Cavitations", "type": "textarea", "section": "Third Molars", "order": 12, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "third_molar_recommendations", "label": "Recommendations", "type": "textarea", "section": "Third Molars", "order": 13, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "sinus_ul", "label": "UL", "type": "textarea", "section": "Sinus Areas", "order": 14, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "sinus_ur", "label": "UR", "type": "textarea", "section": "Sinus Areas", "order": 15, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "existing_rcts", "label": "Existing RCTs", "type": "textarea", "section": "Sinus Areas", "order": 16, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "any_into_sinus", "label": "Any Into Sinus", "type": "checkbox", "section": "Sinus Areas", "order": 17, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "sinus_recommendations", "label": "Recommendations", "type": "textarea", "section": "Sinus Areas", "order": 18, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "periodontal_condition", "label": "Condition", "type": "textarea", "section": "Periodontal", "order": 19, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "tx_recommendations", "label": "Tx Recommendations", "type": "textarea", "section": "Periodontal", "order": 20, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "md_referral", "label": "MD Referral", "type": "checkbox", "section": "Periodontal", "order": 21, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "blood_test", "label": "Blood Test", "type": "checkbox", "section": "Periodontal", "order": 22, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "occlusion", "label": "Occlusion", "type": "textarea", "section": "Occlusion", "order": 23, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "guidance", "label": "Guidance", "type": "textarea", "section": "Occlusion", "order": 24, "active": True, "required": False, "patient_editable": False, "core": True},
    {"key": "occlusion_recommendations", "label": "Recommendations", "type": "textarea", "section": "Occlusion", "order": 25, "active": True, "required": False, "patient_editable": False, "core": True},
]


class DoctorFormConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-doctor form layout: which fields exist, their labels, order,
    section grouping, and whether a patient may fill them in on the
    public self-fill link."""

    __tablename__ = "doctor_form_configs"

    doctor_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("doctor_profiles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # list[FieldConfig] (see app.schemas.form_config.FieldConfig)
    fields: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # S3 object key for the doctor's default patient-document logo -- applied
    # to every new document at creation time unless overridden per-document.
    logo_key: Mapped[str | None] = mapped_column(String(500), nullable=True)