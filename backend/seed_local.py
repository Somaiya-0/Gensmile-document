"""One-off local dev seed: creates tables (if needed) and one doctor login.

Run once before starting uvicorn:
    ./.venv/bin/python3 seed_local.py
"""
import asyncio

from app.core.security import hash_password
from app.db import AsyncSessionLocal, create_database_tables
from app.models import DoctorProfile, UserAccount, UserRole

DOCTOR_EMAIL = "doctor@gensmile-localdev.com"
DOCTOR_PASSWORD = "LocalDev123!"

ADMIN_EMAIL = "admin@gensmile-localdev.com"
ADMIN_PASSWORD = "LocalAdmin123!"


async def _seed_user(db, *, email: str, password: str, full_name: str, role: UserRole) -> bool:
    """Returns True if created, False if it already existed."""
    from sqlalchemy import select

    existing = await db.scalar(select(UserAccount).where(UserAccount.email == email))
    if existing:
        print(f"Already exists: {email}")
        return False

    user = UserAccount(
        role=role,
        email=email,
        full_name=full_name,
        password_hash=hash_password(password),
        is_active=True,
        email_verified=True,
        onboarding_completed=True,
    )
    db.add(user)
    await db.flush()

    if role == UserRole.DOCTOR:
        db.add(DoctorProfile(user_id=user.id))

    await db.commit()
    return True


async def main() -> None:
    await create_database_tables()

    async with AsyncSessionLocal() as db:
        if await _seed_user(db, email=DOCTOR_EMAIL, password=DOCTOR_PASSWORD, full_name="Local Test Doctor", role=UserRole.DOCTOR):
            print(f"Seeded doctor login  -> email: {DOCTOR_EMAIL}  password: {DOCTOR_PASSWORD}")

    async with AsyncSessionLocal() as db:
        if await _seed_user(db, email=ADMIN_EMAIL, password=ADMIN_PASSWORD, full_name="Local Admin", role=UserRole.ADMIN):
            print(f"Seeded admin login   -> email: {ADMIN_EMAIL}  password: {ADMIN_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
