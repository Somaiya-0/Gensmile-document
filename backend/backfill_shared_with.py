"""One-off: add a "Shared with" History entry for every doctor who opened a
share link before that was logged. Dated at their last open (the first open
wasn't recorded). Skips any doctor that already has an entry, so it's safe
to re-run.

    ./.venv/bin/python3 backfill_shared_with.py
"""
import asyncio

from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import DoctorProfile, UserAccount
from app.models.patient_document import PatientDocument, PatientDocumentChangeLog, PatientDocumentSharedAccess


async def main() -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(PatientDocumentSharedAccess, UserAccount.full_name, PatientDocument.doctor_profile_id)
            .join(UserAccount, UserAccount.id == PatientDocumentSharedAccess.user_id)
            .join(PatientDocument, PatientDocument.id == PatientDocumentSharedAccess.document_id)
        )).all()
        added = 0
        for access, opener, profile_id in rows:
            exists = await db.scalar(select(PatientDocumentChangeLog.id).where(
                PatientDocumentChangeLog.document_id == access.document_id,
                PatientDocumentChangeLog.field_label == "Shared with",
                PatientDocumentChangeLog.new_value == opener,
            ).limit(1))
            if exists:
                continue
            sharer = (await db.execute(
                select(PatientDocumentChangeLog.changed_by_user_id, PatientDocumentChangeLog.changed_by_name)
                .where(
                    PatientDocumentChangeLog.document_id == access.document_id,
                    PatientDocumentChangeLog.change_type == "sharing",
                    PatientDocumentChangeLog.field_label == "Doctor-to-doctor link",
                    PatientDocumentChangeLog.new_value.in_(["Yes", "New link generated"]),
                    PatientDocumentChangeLog.created_at <= access.last_opened_at,
                )
                .order_by(PatientDocumentChangeLog.created_at.desc())
                .limit(1)
            )).first()
            if sharer is None:  # link turned on before sharing was logged -> the owner
                sharer = (await db.execute(
                    select(UserAccount.id, UserAccount.full_name)
                    .join(DoctorProfile, DoctorProfile.user_id == UserAccount.id)
                    .where(DoctorProfile.id == profile_id)
                )).first()
            db.add(PatientDocumentChangeLog(
                document_id=access.document_id,
                changed_by_user_id=sharer[0] if sharer else None,
                changed_by_name=sharer[1] if sharer else "Document owner",
                change_type="sharing",
                field_label="Shared with",
                new_value=opener,
                created_at=access.last_opened_at,
            ))
            added += 1
        await db.commit()
        print(f"Added {added} of {len(rows)} 'Shared with' entries.")


if __name__ == "__main__":
    asyncio.run(main())
