"""Doctor/patient-roster helpers the Documents app needs, carried over
unchanged from the full GenSmile app's doctor_controller (which also covers
clinics, availability, simulations, etc. -- none of it used here).

- list_doctor_patients: the "Existing patient" picker on the Documents page.
- create_patient_user_for_doctor / is_placeholder_email: used when a
  document is created for a patient who isn't on the roster yet.
"""

import secrets
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.services.document_events import emit_event
from app.models import (
    DoctorPatient,
    DoctorProfile,
    PatientProfile,
    StaffMember,
    UserAccount,
    UserRole,
)
from app.models.enums import ContactMethod, DoctorPatientStatus
from app.schemas.doctor import DoctorPatientRead


PLACEHOLDER_EMAIL_DOMAIN = "no-email.gensmile.internal"


def is_placeholder_email(email: str | None) -> bool:
    """True for the auto-generated login email of a patient added without a
    real address -- never show this to a doctor as if it were the patient's
    real contact email, and never send mail to it."""
    return bool(email) and email.endswith(f"@{PLACEHOLDER_EMAIL_DOMAIN}")


async def _require_doctor(user: UserAccount, db: AsyncSession) -> DoctorProfile:
    if user.role not in (UserRole.DOCTOR, UserRole.STAFF, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Doctor or staff role required.",
        )
    profile = getattr(user, "doctor_profile", None)
    if profile is None:
        if user.role == UserRole.STAFF:
            row = await db.scalar(
                select(StaffMember)
                .options(selectinload(StaffMember.doctor_profile))
                .where(StaffMember.user_id == user.id)
            )
            profile = row.doctor_profile if row else None
        else:
            profile = await db.scalar(
                select(DoctorProfile).where(DoctorProfile.user_id == user.id)
            )
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found.",
        )
    return profile


async def list_doctor_patients(
    *,
    db: AsyncSession,
    user: UserAccount,
    query: str | None = None,
    status_filter: DoctorPatientStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[DoctorPatientRead], int]:
    profile = await _require_doctor(user, db)
    doctor_id = profile.user_id

    normalized_query = (query or "").strip().lower()

    filters = [DoctorPatient.doctor_user_id == doctor_id]
    if status_filter:
        filters.append(DoctorPatient.status == status_filter)
    else:
        filters.append(DoctorPatient.status != DoctorPatientStatus.INACTIVE)

    stmt = (
        select(DoctorPatient)
        .options(selectinload(DoctorPatient.patient).selectinload(UserAccount.patient_profile))
        .where(*filters)
        .order_by(DoctorPatient.created_at.desc())
    )
    all_doctor_patients = list((await db.scalars(stmt)).all())

    if normalized_query:
        all_doctor_patients = [
            dp for dp in all_doctor_patients
            if normalized_query in (dp.patient.full_name + " " + dp.patient.email).lower()
        ]

    total = len(all_doctor_patients)
    offset = (page - 1) * page_size
    page_items = all_doctor_patients[offset: offset + page_size]

    results: list[DoctorPatientRead] = []
    for dp in page_items:
        patient = dp.patient
        profile = patient.patient_profile

        # No consultation/appointment feature in this app -- always None.
        last_visit = None

        results.append(
            DoctorPatientRead(
                id=dp.id,
                patient_user_id=patient.id,
                full_name=patient.full_name,
                email=None if is_placeholder_email(patient.email) else patient.email,
                phone=profile.phone if profile else "",
                gender=profile.gender if profile else None,
                birth_date=profile.birth_date if profile else None,
                status=dp.status,
                linked_at=dp.created_at,
                last_visit=last_visit,
            )
        )

    return results, total


async def create_patient_user_for_doctor(
    *,
    db: AsyncSession,
    doctor_user_id: UUID,
    full_name: str,
    email: str | None = None,
    phone: str | None = None,
    doctor_profile_id: UUID | None = None,
) -> UUID:
    """Create (or reuse) a roster patient from just a name/contact info --
    used when a patient is implied by other data (e.g. a Patient Document
    created for a new patient) rather than filled in via Add Patient, so
    that patient still shows up on the doctor's Patients list.

    doctor_profile_id: pass it when the caller already has it (avoids an
    extra query here) -- used only to tell the doctor's open Documents pages
    that a new patient appeared in the "existing patient" picker.
    """
    if doctor_profile_id is None:
        doctor_profile_id = await db.scalar(
            select(DoctorProfile.id).where(DoctorProfile.user_id == doctor_user_id)
        )
    normalized_email: str | None = None
    if email:
        normalized_email = email.lower().strip()
        existing_user = await db.scalar(select(UserAccount).where(UserAccount.email == normalized_email))
        if existing_user is not None:
            existing_link = await db.scalar(
                select(DoctorPatient).where(
                    DoctorPatient.doctor_user_id == doctor_user_id,
                    DoctorPatient.patient_user_id == existing_user.id,
                )
            )
            if existing_link is None:
                db.add(DoctorPatient(
                    doctor_user_id=doctor_user_id,
                    patient_user_id=existing_user.id,
                    status=DoctorPatientStatus.ACTIVE,
                ))
                await emit_event(db, doctor_profile_id, {"type": "patients_updated"})
                await db.commit()
            return existing_user.id
    else:
        # No email to match on -- fall back to matching an existing roster
        # patient by name instead of always minting a new one. Without this,
        # every no-email document for "Jane Doe" created a fresh duplicate
        # patient, so the document never showed up under the real Jane Doe's
        # Documents tab.
        existing_link = await db.scalar(
            select(DoctorPatient)
            .join(UserAccount, UserAccount.id == DoctorPatient.patient_user_id)
            .where(
                DoctorPatient.doctor_user_id == doctor_user_id,
                func.lower(UserAccount.full_name) == full_name.strip().lower(),
            )
        )
        if existing_link is not None:
            return existing_link.patient_user_id

        for _ in range(5):
            candidate = f"patient-{secrets.token_hex(8)}@{PLACEHOLDER_EMAIL_DOMAIN}"
            existing = await db.scalar(select(UserAccount).where(UserAccount.email == candidate))
            if existing is None:
                normalized_email = candidate
                break
        if normalized_email is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not generate a placeholder email. Please try again.",
            )

    temp_password = secrets.token_urlsafe(16)
    new_user = UserAccount(
        role=UserRole.PATIENT,
        email=normalized_email,
        full_name=full_name.strip(),
        password_hash=hash_password(temp_password),
        is_active=True,
        onboarding_completed=True,
    )
    db.add(new_user)
    await db.flush()

    db.add(PatientProfile(user_id=new_user.id, phone=phone, preferred_contact_method=ContactMethod.EMAIL))
    db.add(DoctorPatient(
        doctor_user_id=doctor_user_id,
        patient_user_id=new_user.id,
        status=DoctorPatientStatus.ACTIVE,
    ))
    await emit_event(db, doctor_profile_id, {"type": "patients_updated"})
    await db.commit()
    await db.refresh(new_user)
    return new_user.id
