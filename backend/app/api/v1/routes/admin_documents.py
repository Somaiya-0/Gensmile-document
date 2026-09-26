from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_admin, get_db_session
from app.models import DoctorProfile, PatientDocument, UserAccount
from app.schemas.admin import AdminDocumentRead
from app.services import s3_service

router = APIRouter(prefix="/admin/documents", tags=["admin"])


@router.get("", response_model=list[AdminDocumentRead])
async def list_all_documents(
    _admin: UserAccount = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db_session),
) -> list[AdminDocumentRead]:
    stmt = (
        select(PatientDocument, UserAccount.full_name, UserAccount.email)
        .join(DoctorProfile, DoctorProfile.id == PatientDocument.doctor_profile_id)
        .join(UserAccount, UserAccount.id == DoctorProfile.user_id)
        .order_by(PatientDocument.updated_at.desc())
    )
    rows = (await db.execute(stmt)).all()

    return [
        AdminDocumentRead(
            id=doc.id,
            doctor_profile_id=doc.doctor_profile_id,
            doctor_name=doctor_name,
            doctor_email=doctor_email,
            patient_name=doc.patient_name,
            patient_email=doc.patient_email,
            logo_url=s3_service.get_presigned_url(doc.logo_key),
            is_shared=doc.is_shared,
            fill_enabled=doc.fill_enabled,
            patient_submitted_at=doc.patient_submitted_at,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
        for doc, doctor_name, doctor_email in rows
    ]
