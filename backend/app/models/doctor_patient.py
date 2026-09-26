from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import DoctorPatientStatus


class DoctorPatient(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "doctor_patients"
    __table_args__ = (
        UniqueConstraint("doctor_user_id", "patient_user_id"),
    )

    doctor_user_id: Mapped[UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="CASCADE"), index=True)
    patient_user_id: Mapped[UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="CASCADE"), index=True)
    status: Mapped[DoctorPatientStatus] = mapped_column(default=DoctorPatientStatus.PENDING)

    doctor: Mapped["UserAccount"] = relationship(foreign_keys=[doctor_user_id])
    patient: Mapped["UserAccount"] = relationship(foreign_keys=[patient_user_id])
