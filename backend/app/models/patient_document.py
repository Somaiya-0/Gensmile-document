from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PatientDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Patient document form/template created by a doctor.

    Two independent sharing mechanisms live on this model:
      - share_token / is_shared   -> doctor-to-doctor: the same form fields/
        values as the patient self-fill view, but read-only (see
        PatientDocumentPublicRead), plus attached files.
      - fill_token / fill_enabled -> patient self-fill: exposes every
        active field in this document's form_config, editable, no auth required.
    """

    __tablename__ = "patient_documents"

    doctor_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("doctor_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    patient_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    patient_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    patient_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Optional link to an actual patient on the doctor's roster (DoctorPatient /
    # UserAccount). Nullable because documents can also be created for a
    # one-off/new patient that isn't in the roster yet. When set, patient_name/
    # email/phone above are a snapshot taken at creation time.
    patient_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Form fields
    visit_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chief_concern: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_dds_visit: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cbct_taken: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    req_radiologist: Mapped[str | None] = mapped_column(String(255), nullable=True)
    exam_salivary_ph: Mapped[str | None] = mapped_column(String(50), nullable=True)
    recommend_salivary_test: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cbct_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Third molars
    third_molar_ll: Mapped[str | None] = mapped_column(Text, nullable=True)
    third_molar_lr: Mapped[str | None] = mapped_column(Text, nullable=True)
    third_molar_ul: Mapped[str | None] = mapped_column(Text, nullable=True)
    third_molar_ur: Mapped[str | None] = mapped_column(Text, nullable=True)
    cavitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    third_molar_recommendations: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Sinus areas
    sinus_ul: Mapped[str | None] = mapped_column(Text, nullable=True)
    sinus_ur: Mapped[str | None] = mapped_column(Text, nullable=True)
    existing_rcts: Mapped[str | None] = mapped_column(Text, nullable=True)
    any_into_sinus: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    sinus_recommendations: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Periodontal
    periodontal_condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    tx_recommendations: Mapped[str | None] = mapped_column(Text, nullable=True)
    md_referral: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    blood_test: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Occlusion
    occlusion: Mapped[str | None] = mapped_column(Text, nullable=True)
    guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    occlusion_recommendations: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Doctor-defined custom fields (key -> value) added via the Settings
    # form-builder. Fixed columns above stay untouched; anything the doctor
    # adds beyond them lives here instead of a schema migration.
    custom_fields: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Document-specific form configuration (list of FieldConfig dicts).
    # When NULL, falls back to the doctor's default DoctorFormConfig.
    form_config: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # S3 object key for the clinic logo (NOT a public URL -- resolved to a
    # presigned URL at read time via s3_service.get_presigned_url).
    logo_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # --- Doctor-to-doctor file sharing ---
    share_token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- Patient self-fill link ---
    fill_token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    fill_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    patient_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    doctor_profile: Mapped["DoctorProfile"] = relationship(
        lazy="selectin",
    )  # type: ignore[name-defined]

    files: Mapped[list["PatientDocumentFile"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PatientDocumentFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Files (PDF/images) attached to a patient document, stored in S3."""

    __tablename__ = "patient_document_files"

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("patient_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    file_name: Mapped[str] = mapped_column(String(500), nullable=False)

    # S3 object key (private object; resolved to a presigned URL at read time)
    file_key: Mapped[str] = mapped_column(String(500), nullable=False)

    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # pdf | jpg | png | webp | etc.

    file_size: Mapped[int] = mapped_column(Integer, nullable=False)

    uploaded_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    uploaded_by_patient: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    document: Mapped["PatientDocument"] = relationship(
        back_populates="files",
    )