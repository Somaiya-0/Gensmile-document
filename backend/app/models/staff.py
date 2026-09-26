from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import StaffStatus

DEFAULT_PERMISSIONS: dict = {
    "dashboard": True,
    "patients": True,
    "simulations": True,
    "results": True,
    "lab_links": False,
    "patient_documents": True,
    "billing": False,
    "settings": False,
    "affiliate": False,
}


class StaffMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "staff_members"

    doctor_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("doctor_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[StaffStatus] = mapped_column(
        Enum(StaffStatus),
        default=StaffStatus.PENDING,
        nullable=False,
        index=True,
    )
    permissions: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: dict(DEFAULT_PERMISSIONS),
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Why is_active is currently False, if it is. Plain string (not a DB enum)
    # so adding reasons later never needs an ALTER TYPE migration. One of:
    # "manual" (doctor removed them), "capacity_limit" (plan/add-on downgrade
    # pushed them over the cap), "subscription_suspended" (frozen by
    # subscription suspension -- see app.services.subscription_suspension_service).
    # NULL when is_active is True. This distinction is what stops restoration
    # logic from reactivating a staff member who was deliberately removed.
    deactivation_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)

    doctor_profile: Mapped["DoctorProfile"] = relationship(  # type: ignore[name-defined]
        back_populates="managed_staff",
    )