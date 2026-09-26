from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DoctorProfile, UserAccount, UserRole
from app.models.doctor_form_config import DEFAULT_FORM_FIELDS, DoctorFormConfig
from app.models.staff import StaffMember
from app.schemas.form_config import FormConfigUpdate
from app.schemas.patient_document import LogoUploadResponse
from app.services import s3_service


async def get_or_create_form_config_for_doctor(
    db: AsyncSession, doctor_profile_id: UUID
) -> DoctorFormConfig:
    stmt = select(DoctorFormConfig).where(
        DoctorFormConfig.doctor_profile_id == doctor_profile_id
    )
    config = await db.scalar(stmt)

    if not config:
        config = DoctorFormConfig(
            doctor_profile_id=doctor_profile_id,
            fields=DEFAULT_FORM_FIELDS,
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)

    return config


async def _require_doctor(db: AsyncSession, user: UserAccount) -> DoctorProfile:
    if user.role not in (UserRole.DOCTOR, UserRole.STAFF):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Doctor or staff role required.")

    if user.role == UserRole.STAFF:
        member = await db.scalar(select(StaffMember).where(StaffMember.user_id == user.id))
        if member is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member record not found.")
        profile = await db.scalar(select(DoctorProfile).where(DoctorProfile.id == member.doctor_profile_id))
    else:
        profile = await db.scalar(select(DoctorProfile).where(DoctorProfile.user_id == user.id))

    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found.")
    return profile


async def get_or_create_form_config(db: AsyncSession, user: UserAccount) -> DoctorFormConfig:
    profile = await _require_doctor(db, user)
    return await get_or_create_form_config_for_doctor(db, profile.id)


async def update_form_config(
    db: AsyncSession, user: UserAccount, payload: FormConfigUpdate
) -> DoctorFormConfig:
    config = await get_or_create_form_config(db, user)

    seen_keys: set[str] = set()
    for field in payload.fields:
        if field.key in seen_keys:
            raise ValueError(f"Duplicate field key: {field.key}")
        seen_keys.add(field.key)

    core_keys = {f["key"] for f in DEFAULT_FORM_FIELDS}
    for field in payload.fields:
        if field.key in core_keys and not field.core:
            raise ValueError(
                f"'{field.key}' is a built-in field and must stay marked as core "
                "(hide it with active=false instead of removing it)"
            )

    config.fields = [f.model_dump() for f in payload.fields]
    await db.commit()
    await db.refresh(config)
    return config


async def upload_default_logo(
    db: AsyncSession, user: UserAccount, file: UploadFile
) -> LogoUploadResponse:
    """Set the doctor-wide default logo, applied to every new patient
    document going forward (a document can still be given its own logo,
    which overrides this default for that one document only)."""
    config = await get_or_create_form_config(db, user)

    key, _content_type, _size = await s3_service.upload_file_to_s3(
        file, prefix="logos", allowed_types=s3_service.ALLOWED_LOGO_TYPES
    )

    old_key = config.logo_key
    config.logo_key = key
    await db.commit()

    if old_key:
        await s3_service.delete_file_from_s3(old_key)

    return LogoUploadResponse(logo_url=s3_service.get_presigned_url(key))