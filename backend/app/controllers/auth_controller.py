from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    get_refresh_token_expiry,
    get_password_reset_expiry,
    hash_password,
    hash_password_reset_token,
    hash_refresh_token,
    verify_password,
)
from app.models import (
    DoctorProfile,
    PasswordResetTokenSession,
    RefreshTokenSession,
    UserAccount,
    UserRole,
)
from app.models.enums import StaffStatus
from app.schemas.auth import (
    CurrentUserResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LogoutResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    RefreshTokenRequest,
    TokenPairResponse,
)
from app.services.email_service import is_smtp_configured, send_password_reset_email

settings = get_settings()


async def login_user(
    *, db: AsyncSession, payload: LoginRequest, ip_address: str | None = None, user_agent: str | None = None,
) -> TokenPairResponse:
    user = await db.scalar(
        select(UserAccount)
        .options(
            selectinload(UserAccount.doctor_profile),
            selectinload(UserAccount.patient_profile),
        )
        .where(UserAccount.email == payload.email.lower().strip())
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No account found with this email.",
        )

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active yet. Please complete onboarding first.",
        )
        
    if user.role == UserRole.STAFF:
        from app.models.staff import StaffMember

        staff_member = await db.scalar(
            select(StaffMember).where(StaffMember.user_id == user.id)
        )
        if staff_member is not None and (
            not staff_member.is_active or staff_member.status == StaffStatus.INACTIVE
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your staff account has been deactivated. Please contact your doctor.",
            )

    return await issue_token_pair(db=db, user=user, ip_address=ip_address, user_agent=user_agent)


async def request_password_reset(
    *,
    db: AsyncSession,
    payload: ForgotPasswordRequest,
) -> ForgotPasswordResponse:
    user = await db.scalar(
        select(UserAccount).where(UserAccount.email == payload.email.lower().strip())
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email.",
        )

    active_tokens = await db.scalars(
        select(PasswordResetTokenSession).where(
            PasswordResetTokenSession.user_id == user.id,
            PasswordResetTokenSession.used_at.is_(None),
        )
    )

    now = datetime.now(timezone.utc)
    for active_token in active_tokens:
        active_token.used_at = now

    reset_token = create_password_reset_token()
    reset_url = (
        f"{settings.frontend_base_url.rstrip('/')}/reset-password?token={reset_token}"
    )
    reset_session = PasswordResetTokenSession(
        user_id=user.id,
        token_hash=hash_password_reset_token(reset_token),
        expires_at=get_password_reset_expiry(),
    )
    db.add(reset_session)
    await db.commit()

    if is_smtp_configured():
        try:
            await send_password_reset_email(
                recipient_email=user.email,
                reset_url=reset_url,
            )
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Password reset email failed to send: %s", exc
            )

    return ForgotPasswordResponse(
        message="A password reset link has been generated.",
        reset_token=reset_token if settings.environment.lower() != "production" else None,
        reset_url=reset_url if settings.environment.lower() != "production" else None,
    )


async def reset_password(
    *,
    db: AsyncSession,
    payload: ResetPasswordRequest,
) -> ResetPasswordResponse:
    reset_session = await db.scalar(
        select(PasswordResetTokenSession)
        .options(selectinload(PasswordResetTokenSession.user))
        .where(
            PasswordResetTokenSession.token_hash
            == hash_password_reset_token(payload.token)
        )
    )

    if reset_session is None or not reset_session.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link is invalid or has expired.",
        )

    if reset_session.user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The password reset link is no longer valid.",
        )

    reset_session.user.password_hash = hash_password(payload.password)
    reset_session.used_at = datetime.now(timezone.utc)

    refresh_sessions = await db.scalars(
        select(RefreshTokenSession).where(RefreshTokenSession.user_id == reset_session.user.id)
    )
    for refresh_session in refresh_sessions:
        if refresh_session.revoked_at is None:
            refresh_session.revoked_at = reset_session.used_at
            refresh_session.last_used_at = reset_session.used_at

    await db.commit()

    return ResetPasswordResponse(message="Password reset successfully.")


async def accept_invitation(
    *,
    db: AsyncSession,
    payload: ResetPasswordRequest,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> TokenPairResponse:
    from app.models.enums import StaffStatus
    from app.models.staff import StaffMember

    reset_session = await db.scalar(
        select(PasswordResetTokenSession)
        .options(
            selectinload(PasswordResetTokenSession.user).selectinload(UserAccount.patient_profile),
            selectinload(PasswordResetTokenSession.user).selectinload(UserAccount.doctor_profile),
        )
        .where(
            PasswordResetTokenSession.token_hash
            == hash_password_reset_token(payload.token)
        )
    )

    if reset_session is None or not reset_session.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation link is invalid or has expired.",
        )

    user = reset_session.user
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The invitation link is no longer valid.",
        )

    user.password_hash = hash_password(payload.password)
    user.is_active = True
    reset_session.used_at = datetime.now(timezone.utc)

    if user.role == UserRole.STAFF:
        staff_member = await db.scalar(
            select(StaffMember).where(StaffMember.user_id == user.id)
        )
        if staff_member:
            staff_member.status = StaffStatus.ACTIVE
            staff_member.is_active = True
            
    if user.role == UserRole.PATIENT:
        from app.models.doctor_patient import DoctorPatient
        from app.models.enums import DoctorPatientStatus
        
        doctor_patient = await db.scalar(
            select(DoctorPatient).where(
                DoctorPatient.patient_user_id == user.id,
                DoctorPatient.status == DoctorPatientStatus.PENDING,
            )
        )
        if doctor_patient:
            doctor_patient.status = DoctorPatientStatus.ACTIVE

    refresh_sessions = await db.scalars(
        select(RefreshTokenSession).where(RefreshTokenSession.user_id == user.id)
    )
    for refresh_session in refresh_sessions:
        if refresh_session.revoked_at is None:
            refresh_session.revoked_at = reset_session.used_at
            refresh_session.last_used_at = reset_session.used_at

    return await issue_token_pair(db=db, user=user, ip_address=ip_address, user_agent=user_agent)


async def refresh_access_token(
    *,
    db: AsyncSession,
    payload: RefreshTokenRequest,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> TokenPairResponse:
    refresh_session = await db.scalar(
        select(RefreshTokenSession)
        .options(
            selectinload(RefreshTokenSession.user).selectinload(UserAccount.patient_profile),
            selectinload(RefreshTokenSession.user).selectinload(UserAccount.doctor_profile),
        )
        .where(
            RefreshTokenSession.token_hash == hash_refresh_token(payload.refresh_token)
        )
    )

    if refresh_session is None or not refresh_session.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    user = refresh_session.user
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user not found.",
        )

    if user.role == UserRole.STAFF:
        from app.models.staff import StaffMember
        staff_member = await db.scalar(
            select(StaffMember).where(StaffMember.user_id == user.id)
        )
        if staff_member is not None and (
            not staff_member.is_active or staff_member.status == StaffStatus.INACTIVE
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Your staff account has been deactivated. Please contact your doctor.",
            )

    refresh_session.revoked_at = datetime.now(timezone.utc)
    refresh_session.last_used_at = refresh_session.revoked_at

    token_response = await issue_token_pair(
        db=db,
        user=user,
        replaced_token=refresh_session,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await db.commit()
    return token_response


async def logout_user(
    *,
    db: AsyncSession,
    payload: RefreshTokenRequest,
) -> LogoutResponse:
    refresh_session = await db.scalar(
        select(RefreshTokenSession).where(
            RefreshTokenSession.token_hash == hash_refresh_token(payload.refresh_token)
        )
    )

    if refresh_session and refresh_session.revoked_at is None:
        refresh_session.revoked_at = datetime.now(timezone.utc)
        refresh_session.last_used_at = refresh_session.revoked_at
        await db.commit()

    return LogoutResponse(message="Logged out successfully.")


def build_current_user_response(user: UserAccount) -> CurrentUserResponse:
    return CurrentUserResponse(
        user=user,
        doctor_profile=user.doctor_profile,
        patient_profile=user.patient_profile,
    )


async def issue_token_pair(
    *,
    db: AsyncSession,
    user: UserAccount,
    replaced_token: RefreshTokenSession | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> TokenPairResponse:
    access_token, access_token_expires_at = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role.value,
    )
    raw_refresh_token = create_refresh_token()
    refresh_token_expires_at = get_refresh_token_expiry()

    refresh_session = RefreshTokenSession(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh_token),
        expires_at=refresh_token_expires_at,
        last_used_at=datetime.now(timezone.utc),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(refresh_session)
    await db.flush()

    if replaced_token is not None:
        replaced_token.replaced_by_token_id = refresh_session.id
    else:
        await db.commit()

    return TokenPairResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
        access_token_expires_at=access_token_expires_at,
        refresh_token_expires_at=refresh_token_expires_at,
        user=user,
    )
