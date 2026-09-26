from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now
from app.models.enums import ContactMethod, UserRole


class UserAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_accounts"

    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        server_default="false",
    )
    onboarding_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    doctor_profile: Mapped["DoctorProfile | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    patient_profile: Mapped["PatientProfile | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[list["RefreshTokenSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class DoctorProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "doctor_profiles"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    specialty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    affiliation: Mapped[str | None] = mapped_column(String(500), nullable=True)
    license_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    user: Mapped[UserAccount] = relationship(back_populates="doctor_profile")
    managed_staff: Mapped[list["StaffMember"]] = relationship(
        back_populates="doctor_profile",
        cascade="all, delete-orphan",
        order_by="StaffMember.sort_order",
    )


class PatientProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "patient_profiles"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(50), nullable=True)
    blood_group: Mapped[str | None] = mapped_column(String(10), nullable=True)
    full_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    street_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    preferred_contact_method: Mapped[ContactMethod] = mapped_column(
        Enum(ContactMethod),
        nullable=False,
    )

    user: Mapped[UserAccount] = relationship(back_populates="patient_profile")


class RefreshTokenSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "refresh_token_sessions"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_token_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("refresh_token_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Captured at login/refresh time for admin-panel login-activity tracking
    # (see app.core.user_agent for the device_label parsing). Nullable since
    # rows created before this field existed won't have it.
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user: Mapped[UserAccount] = relationship(back_populates="refresh_tokens")
    replaced_by: Mapped["RefreshTokenSession | None"] = relationship(
        remote_side="RefreshTokenSession.id",
        uselist=False,
    )

    @property
    def is_active(self) -> bool:
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            # SQLite (used in tests) doesn't round-trip tzinfo on
            # DateTime(timezone=True) columns; Postgres always does.
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return self.revoked_at is None and expires_at > utc_now()


class PasswordResetTokenSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "password_reset_token_sessions"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[UserAccount] = relationship()

    @property
    def is_active(self) -> bool:
        return self.used_at is None and self.expires_at > utc_now()


class EmailVerificationToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "email_verification_tokens"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[UserAccount] = relationship()

    @property
    def is_active(self) -> bool:
        return self.used_at is None and self.expires_at > utc_now()