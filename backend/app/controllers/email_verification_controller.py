import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models import EmailVerificationToken, UserAccount
from app.services.email_service import is_smtp_configured, send_email_verification_email

settings = get_settings()


def _create_raw_token() -> str:
    return secrets.token_urlsafe(32)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(
        hours=settings.email_verification_token_expire_hours
    )


async def send_verification_email_for_user(
    *, db: AsyncSession, user: UserAccount
) -> None:
    """
    Create a new email verification token for the user and send the email.
    Any previous unused tokens for this user are invalidated first.
    Called after onboarding completion.
    """
    if user.email_verified:
        return  # Nothing to do

    # Invalidate existing active tokens
    existing = await db.scalars(
        select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
        )
    )
    now = datetime.now(timezone.utc)
    for token in existing:
        token.used_at = now  # mark as consumed to prevent reuse

    raw_token = _create_raw_token()
    verification_url = (
        f"{settings.frontend_base_url.rstrip('/')}/verify-email?token={raw_token}"
    )

    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=_hash_token(raw_token),
            expires_at=_expiry(),
        )
    )
    await db.commit()

    if is_smtp_configured():
        await send_email_verification_email(
            recipient_email=user.email,
            recipient_name=user.full_name,
            verification_url=verification_url,
        )


async def verify_email(*, db: AsyncSession, token: str) -> dict:
    """
    Mark the user's email as verified using the supplied raw token.
    Returns a success message dict.
    """
    token_session = await db.scalar(
        select(EmailVerificationToken)
        .options(selectinload(EmailVerificationToken.user))
        .where(EmailVerificationToken.token_hash == _hash_token(token))
    )

    if token_session is None or not token_session.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification link is invalid or has expired.",
        )

    if token_session.user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account not found.",
        )

    token_session.user.email_verified = True
    token_session.used_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": "Email address verified successfully."}


async def resend_verification_email(*, db: AsyncSession, user: UserAccount) -> dict:
    """Re-send the verification email for an already-registered user."""
    if user.email_verified:
        return {"message": "Your email address is already verified."}

    await send_verification_email_for_user(db=db, user=user)
    return {"message": "Verification email sent. Please check your inbox."}
