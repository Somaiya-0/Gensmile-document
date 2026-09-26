from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_admin, get_db_session
from app.core.security import hash_password
from app.models import DoctorProfile, UserAccount, UserRole
from app.schemas.admin import AdminDoctorCreate, AdminDoctorRead

router = APIRouter(prefix="/admin/doctors", tags=["admin"])


@router.get("", response_model=list[AdminDoctorRead])
async def list_doctors(
    _admin: UserAccount = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db_session),
) -> list[UserAccount]:
    result = await db.scalars(
        select(UserAccount)
        .where(UserAccount.role == UserRole.DOCTOR)
        .order_by(UserAccount.created_at.desc())
    )
    return list(result.all())


@router.post("", response_model=AdminDoctorRead, status_code=status.HTTP_201_CREATED)
async def create_doctor(
    payload: AdminDoctorCreate,
    _admin: UserAccount = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db_session),
) -> UserAccount:
    existing = await db.scalar(select(UserAccount).where(UserAccount.email == payload.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = UserAccount(
        role=UserRole.DOCTOR,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        is_active=True,
        email_verified=True,
        onboarding_completed=True,
    )
    db.add(user)
    await db.flush()

    db.add(DoctorProfile(user_id=user.id))
    await db.commit()
    await db.refresh(user)

    return user


@router.delete("/{doctor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_doctor(
    doctor_id: UUID,
    _admin: UserAccount = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    doctor = await db.scalar(
        select(UserAccount).where(UserAccount.id == doctor_id, UserAccount.role == UserRole.DOCTOR)
    )
    if doctor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")

    # DoctorProfile, and everything under it (patients, documents, staff,
    # clinics, lab links, embed links...), cascades at the DB level -- see
    # DoctorProfile.user_id's ondelete="CASCADE" in app/models/onboarding.py.
    await db.delete(doctor)
    await db.commit()
