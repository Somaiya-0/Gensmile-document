import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from app.core.config import get_settings

settings = get_settings()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    password_hash = hashlib.scrypt(
        password=password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
    )
    encoded_salt = base64.b64encode(salt).decode("utf-8")
    encoded_hash = base64.b64encode(password_hash).decode("utf-8")
    return f"scrypt$16384$8$1${encoded_salt}${encoded_hash}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        _, n, r, p, encoded_salt, expected_hash = stored_hash.split("$", maxsplit=5)
    except ValueError:
        return False

    salt = base64.b64decode(encoded_salt.encode("utf-8"))
    password_hash = hashlib.scrypt(
        password=password.encode("utf-8"),
        salt=salt,
        n=int(n),
        r=int(r),
        p=int(p),
    )
    encoded_hash = base64.b64encode(password_hash).decode("utf-8")
    return secrets.compare_digest(encoded_hash, expected_hash)


def create_access_token(
    *,
    user_id: UUID,
    email: str,
    role: str,
) -> tuple[str, datetime]:
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "type": "access",
        "iss": settings.jwt_issuer,
        "exp": expires_at,
        "iat": issued_at,
    }
    token = jwt.encode(
        payload,
        settings.access_token_secret,
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.access_token_secret,
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
    )


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(refresh_token: str) -> str:
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()


def get_refresh_token_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)


def create_password_reset_token() -> str:
    return secrets.token_urlsafe(48)


def hash_password_reset_token(reset_token: str) -> str:
    return hashlib.sha256(reset_token.encode("utf-8")).hexdigest()


def get_password_reset_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(
        minutes=settings.password_reset_token_expire_minutes
    )


def get_invitation_token_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(
        hours=settings.invitation_token_expire_hours
    )


def is_jwt_expired(error: Exception) -> bool:
    return isinstance(error, ExpiredSignatureError)


def is_jwt_invalid(error: Exception) -> bool:
    return isinstance(error, InvalidTokenError)
