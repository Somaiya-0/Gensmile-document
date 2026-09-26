from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import decode_access_token, is_jwt_expired, is_jwt_invalid
from app.db.session import async_session_factory
from app.models import DoctorProfile, StaffMember, UserAccount
from app.models.enums import StaffStatus, UserRole


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> UserAccount:
    try:
        payload = decode_access_token(credentials.credentials)
    except Exception as error:
        if is_jwt_expired(error) or is_jwt_invalid(error):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token.",
            ) from error
        raise

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token type.",
        )

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token payload.",
        )

    user = await db.scalar(
        select(UserAccount)
        .options(
            selectinload(UserAccount.doctor_profile),
            selectinload(UserAccount.patient_profile),
        )
        .where(UserAccount.id == UUID(subject))
    )

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user not found.",
        )

    # For staff users: attach their own StaffMember record and permissions as private attrs.
    # Never overwrite user.doctor_profile – that would escalate privileges.
    if user.role == UserRole.STAFF:
        staff_member = await db.scalar(
            select(StaffMember)
            .options(selectinload(StaffMember.doctor_profile))
            .where(StaffMember.user_id == user.id)
        )
        if staff_member:
            # A deactivated staff member (fired, or their doctor's subscription
            # froze -- see subscription_suspension_service) must lose access
            # immediately, not just at their next login. login_user already
            # blocks a fresh login; this is the actual per-request chokepoint
            # every authenticated route goes through, so it's what makes an
            # already-issued access token stop working too.
            if not staff_member.is_active or staff_member.status == StaffStatus.INACTIVE:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Your staff account has been deactivated. Please contact your doctor.",
                )
            user._staff_member = staff_member  # type: ignore[attr-defined]
            user._staff_permissions = staff_member.permissions  # type: ignore[attr-defined]
            user.doctor_profile = None  # type: ignore[assignment]

    return user


async def get_current_admin(
    user: UserAccount = Depends(get_current_user),
) -> UserAccount:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden — administrator role required.",
        )
    return user
