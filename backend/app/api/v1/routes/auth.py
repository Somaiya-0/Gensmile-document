from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.ip_blocklist import record_strike
from app.core.rate_limit import limiter
from app.api.dependencies import get_current_user, get_db_session
from app.controllers.auth_controller import (
    accept_invitation,
    build_current_user_response,
    login_user,
    logout_user,
    request_password_reset,
    reset_password,
    refresh_access_token,
)
from app.controllers.email_verification_controller import (
    resend_verification_email,
    verify_email,
)
from app.models import UserAccount
from app.schemas.auth import (
    CurrentUserResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LogoutRequest,
    LogoutResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    RefreshTokenRequest,
    TokenPairResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_401 = {401: {"description": "Missing or invalid access token"}}


@router.post(
    "/login",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
    summary="Log in",
    description=(
        "Authenticate with email and password. "
        "Returns an **access token** (expires in 30 min) and a **refresh token** (expires in 14 days). "
        "Store the refresh token securely and use it with `POST /auth/refresh` to obtain a new pair "
        "without prompting the user to log in again."
    ),
    responses={401: {"description": "Invalid credentials"}, 429: {"description": "Too many requests"}},
)
@limiter.limit(get_settings().rate_limit_login)
async def login(
    request: Request,
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenPairResponse:
    try:
        return await login_user(
            db=db,
            payload=payload,
            ip_address=get_remote_address(request),
            user_agent=request.headers.get("user-agent"),
        )
    except HTTPException as e:
        if e.status_code == status.HTTP_401_UNAUTHORIZED:
            # A wrong-credentials attempt counts toward an outright IP block
            # too, not just this request's own 401 -- see app.core.ip_blocklist.
            record_strike(get_remote_address(request))
        raise


@router.post(
    "/refresh",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description=(
        "Exchange a valid **refresh token** for a new access/refresh token pair. "
        "The old refresh token is invalidated after a successful call."
    ),
    responses={401: {"description": "Refresh token is invalid or expired"}},
)
async def refresh(
    request: Request,
    payload: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenPairResponse:
    return await refresh_access_token(
        db=db,
        payload=payload,
        ip_address=get_remote_address(request),
        user_agent=request.headers.get("user-agent"),
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Log out",
    description=(
        "Invalidate the supplied **refresh token** on the server side. "
        "The client should also discard both tokens locally."
    ),
)
async def logout(
    payload: LogoutRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> LogoutResponse:
    return await logout_user(db=db, payload=payload)


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    description=(
        "Send a password-reset email to the given address. Returns `404` if no "
        "account exists with that email. The reset link expires in **30 minutes**."
    ),
    responses={404: {"description": "No account found with this email"}},
)
@limiter.limit(get_settings().rate_limit_forgot_password)
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ForgotPasswordResponse:
    return await request_password_reset(db=db, payload=payload)


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset password",
    description=(
        "Set a new password using the token received via the password-reset email. "
        "The token is single-use and expires after **30 minutes**."
    ),
    responses={400: {"description": "Token is invalid or expired"}},
)
async def reset_password_route(
    payload: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResetPasswordResponse:
    return await reset_password(db=db, payload=payload)


@router.post(
    "/accept-invitation",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
    summary="Accept an invitation",
    description=(
        "Accept an invitation using a generated token, set the password, activate the user, "
        "and log in immediately."
    ),
    responses={400: {"description": "Token is invalid or expired"}},
)
async def accept_invitation_route(
    request: Request,
    payload: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenPairResponse:
    return await accept_invitation(
        db=db,
        payload=payload,
        ip_address=get_remote_address(request),
        user_agent=request.headers.get("user-agent"),
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user",
    description=(
        "Return the profile of the authenticated user including their role, "
        "linked doctor or patient profile, and account status. "
        "Use this endpoint after login to bootstrap the frontend session."
    ),
    responses=_401,
)
async def me(
    current_user: Annotated[UserAccount, Depends(get_current_user)],
) -> CurrentUserResponse:
    return build_current_user_response(current_user)


@router.post(
    "/verify-email",
    status_code=status.HTTP_200_OK,
    summary="Verify email address",
    description=(
        "Confirm an email address using the token sent to the user after onboarding. "
        "The token is single-use and expires after the configured number of hours (default 24)."
    ),
    responses={400: {"description": "Token is invalid or expired"}},
)
async def verify_email_route(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    return await verify_email(db=db, token=token)


@router.post(
    "/resend-verification",
    status_code=status.HTTP_200_OK,
    summary="Resend verification email",
    description="Re-send the email verification link for the authenticated user.",
    responses=_401,
)
async def resend_verification_route(
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    return await resend_verification_email(db=db, user=current_user)
