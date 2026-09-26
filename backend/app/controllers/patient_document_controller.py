import secrets
import io
import os
import zipfile
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.controllers.form_config_controller import get_or_create_form_config_for_doctor
from app.services.document_events import emit_event
from app.models import DoctorPatient, DoctorProfile, PatientProfile, UserAccount, UserRole
from app.models.staff import StaffMember
from app.models.base import utc_now
from app.models.patient_document import PatientDocument, PatientDocumentFile
from app.schemas.patient_document import (
    LogoUploadResponse,
    PatientDocumentCreate,
    PatientDocumentFileRead,
    PatientDocumentPublicRead,
    PatientDocumentRead,
    PatientDocumentUpdate,
    PatientFillFormRead,
    PatientFillFormSubmit,
)
from app.services import s3_service

FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")


def _new_token() -> str:
    return secrets.token_urlsafe(24)


async def _require_doctor(db: AsyncSession, user: UserAccount) -> DoctorProfile:
    if user.role not in (UserRole.DOCTOR, UserRole.STAFF):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Doctor or staff role required.")

    if user.role == UserRole.STAFF:
        member = await db.scalar(select(StaffMember).where(StaffMember.user_id == user.id))
        if member is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member record not found.")
        # The Documents section isn't in the sidebar -- it's reached by a
        # direct link -- so the staff permission has to be enforced here, not
        # just by hiding a nav item. A missing key means allowed (it predates
        # some staff accounts); only an explicit False blocks.
        if (member.permissions or {}).get("patient_documents") is False:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to Documents.")
        profile = await db.scalar(select(DoctorProfile).where(DoctorProfile.id == member.doctor_profile_id))
    else:
        profile = await db.scalar(select(DoctorProfile).where(DoctorProfile.user_id == user.id))

    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found.")
    return profile


def _doctor_display_name(doc: PatientDocument) -> str:
    profile = doc.doctor_profile
    return (
        getattr(profile, "full_name", None)
        or getattr(profile, "display_name", None)
        or getattr(profile, "name", None)
        or "Your Doctor"
    )


def _file_read(f: PatientDocumentFile) -> PatientDocumentFileRead:
    return PatientDocumentFileRead(
        id=f.id,
        file_name=f.file_name,
        file_type=f.file_type,
        file_size=f.file_size,
        file_url=s3_service.get_presigned_url(f.file_key, download_filename=f.file_name),
        uploaded_by_patient=f.uploaded_by_patient,
        created_at=f.created_at,
    )


def _document_read(doc: PatientDocument) -> PatientDocumentRead:
    return PatientDocumentRead(
        id=doc.id,
        doctor_profile_id=doc.doctor_profile_id,
        patient_name=doc.patient_name,
        patient_email=doc.patient_email,
        patient_phone=doc.patient_phone,
        visit_date=doc.visit_date,
        chief_concern=doc.chief_concern,
        last_dds_visit=doc.last_dds_visit,
        cbct_taken=doc.cbct_taken,
        req_radiologist=doc.req_radiologist,
        exam_salivary_ph=doc.exam_salivary_ph,
        recommend_salivary_test=doc.recommend_salivary_test,
        cbct_notes=doc.cbct_notes,
        third_molar_ll=doc.third_molar_ll,
        third_molar_lr=doc.third_molar_lr,
        third_molar_ul=doc.third_molar_ul,
        third_molar_ur=doc.third_molar_ur,
        cavitations=doc.cavitations,
        third_molar_recommendations=doc.third_molar_recommendations,
        sinus_ul=doc.sinus_ul,
        sinus_ur=doc.sinus_ur,
        existing_rcts=doc.existing_rcts,
        any_into_sinus=doc.any_into_sinus,
        sinus_recommendations=doc.sinus_recommendations,
        periodontal_condition=doc.periodontal_condition,
        tx_recommendations=doc.tx_recommendations,
        md_referral=doc.md_referral,
        blood_test=doc.blood_test,
        occlusion=doc.occlusion,
        guidance=doc.guidance,
        occlusion_recommendations=doc.occlusion_recommendations,
        custom_fields=doc.custom_fields or {},
        is_active=doc.is_active,
        logo_url=s3_service.get_presigned_url(doc.logo_key),
        form_config=doc.form_config,
        share_token=doc.share_token,
        is_shared=doc.is_shared,
        share_url=(
            f"{FRONTEND_BASE_URL}/doctor-to-doctor/documents/{doc.share_token}"
            if doc.is_shared
            else None
        ),
        fill_token=doc.fill_token,
        fill_enabled=doc.fill_enabled,
        fill_url=(
            f"{FRONTEND_BASE_URL}/patient-document/{doc.fill_token}"
            if doc.fill_enabled
            else None
        ),
        patient_submitted_at=doc.patient_submitted_at,
        files=[_file_read(f) for f in doc.files],
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


async def _get_owned_document(
    db: AsyncSession, user: UserAccount, document_id: UUID
) -> PatientDocument | None:
    profile = await _require_doctor(db, user)
    stmt = select(PatientDocument).where(
        PatientDocument.id == document_id,
        PatientDocument.doctor_profile_id == profile.id,
    )
    return await db.scalar(stmt)


async def list_patient_documents(db: AsyncSession, user: UserAccount) -> list[PatientDocumentRead]:
    profile = await _require_doctor(db, user)
    stmt = (
        select(PatientDocument)
        .where(PatientDocument.doctor_profile_id == profile.id)
        .order_by(PatientDocument.updated_at.desc())
    )
    docs = (await db.scalars(stmt)).all()
    return [_document_read(d) for d in docs]


async def create_patient_document(
    db: AsyncSession, user: UserAccount, payload: PatientDocumentCreate
) -> PatientDocumentRead:
    profile = await _require_doctor(db, user)

    # Get doctor's default form config (fields only -- each document's logo is
    # independent, never inherited from a previous document) to copy here.
    try:
        doctor_config = await get_or_create_form_config_for_doctor(db, profile.id)
        default_fields = doctor_config.fields if doctor_config else None
    except Exception:
        default_fields = None

    data = payload.model_dump()

    if data["patient_user_id"] is not None:
        dp = await db.scalar(
            select(DoctorPatient)
            .options(
                selectinload(DoctorPatient.patient).selectinload(UserAccount.patient_profile)
            )
            .where(
                DoctorPatient.doctor_user_id == profile.user_id,
                DoctorPatient.patient_user_id == data["patient_user_id"],
            )
        )
        if dp is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found on your roster.",
            )
        from app.controllers.doctor_patient_controller import is_placeholder_email

        patient = dp.patient
        data["patient_name"] = patient.full_name
        # patient.email is an auto-generated login placeholder for patients
        # added without a real address -- never surface it on the document
        # as if it were their real email.
        data["patient_email"] = None if is_placeholder_email(patient.email) else patient.email
        data["patient_phone"] = patient.patient_profile.phone if patient.patient_profile else None

        existing = await db.scalar(
            select(PatientDocument).where(
                PatientDocument.doctor_profile_id == profile.id,
                PatientDocument.patient_user_id == data["patient_user_id"],
            )
        )
        if existing is not None:
            existing.patient_name = data["patient_name"]
            existing.patient_email = data["patient_email"]
            existing.patient_phone = data["patient_phone"]
            await emit_event(db, profile.id, {"type": "document_updated", "document_id": str(existing.id)})
            await db.commit()
            await db.refresh(existing)
            return _document_read(existing)
    elif not data["patient_name"].strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="patient_name is required when patient_user_id is not set.",
        )
    else:
        # No existing patient was picked -- create a roster patient from the
        # name/contact info given, so this document's patient also shows up
        # on the doctor's Patients list instead of only existing as a name
        # on this one document.
        from app.controllers.doctor_patient_controller import create_patient_user_for_doctor
        data["patient_user_id"] = await create_patient_user_for_doctor(
            db=db,
            doctor_user_id=profile.user_id,
            full_name=data["patient_name"].strip(),
            email=data.get("patient_email"),
            phone=data.get("patient_phone"),
            doctor_profile_id=profile.id,
        )

    doc = PatientDocument(
        doctor_profile_id=profile.id,
        share_token=_new_token(),
        fill_token=_new_token(),
        form_config=default_fields,  # Copy default config
        **data,
    )
    db.add(doc)
    await db.flush()  # populate doc.id (client-side default) before it's used below
    await emit_event(db, profile.id, {"type": "document_updated", "document_id": str(doc.id)})
    await db.commit()
    await db.refresh(doc)
    return _document_read(doc)


async def get_patient_document(
    db: AsyncSession, user: UserAccount, document_id: UUID
) -> PatientDocumentRead | None:
    doc = await _get_owned_document(db, user, document_id)
    return _document_read(doc) if doc else None


def _pdf_field_value(doc: PatientDocument, field: dict) -> str:
    key = field.get("key", "")
    value = getattr(doc, key, None) if field.get("core") else (doc.custom_fields or {}).get(key)
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)


async def _resolve_form_fields(db: AsyncSession, doc: PatientDocument) -> list[dict]:
    if doc.form_config is not None:
        return doc.form_config
    try:
        config = await get_or_create_form_config_for_doctor(db, doc.doctor_profile_id)
        return config.fields if config else []
    except Exception:
        return []


def _build_patient_document_pdf(doc: PatientDocument, fields: list[dict]) -> bytes:
    """Render this document's form data as a PDF -- mirrors the on-screen
    print view (PatientDocumentPrintPage) but generated server-side so it
    can be bundled straight into the download-zip with no browser step."""
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("DocTitle", parent=styles["Heading1"], fontSize=16, spaceAfter=2)
    meta_style = ParagraphStyle("Meta", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#6b7280"))
    section_style = ParagraphStyle("Section", parent=styles["Heading3"], fontSize=11, textColor=colors.HexColor("#1d4ed8"), spaceBefore=12, spaceAfter=4)
    label_style = ParagraphStyle("Label", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#6b7280"))
    value_style = ParagraphStyle("Value", parent=styles["Normal"], fontSize=9)

    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=A4, topMargin=16 * mm, bottomMargin=16 * mm, leftMargin=16 * mm, rightMargin=16 * mm)

    contact = doc.patient_phone or doc.patient_email or "—"
    story = [
        Paragraph("Patient Clinical Document", title_style),
        Paragraph(f"Generated {utc_now().strftime('%Y-%m-%d')}", meta_style),
        Spacer(1, 10),
        Table(
            [[
                Paragraph(f"<b>Patient</b><br/>{escape(doc.patient_name)}", value_style),
                Paragraph(f"<b>Visit Date</b><br/>{doc.visit_date.strftime('%Y-%m-%d') if doc.visit_date else '—'}", value_style),
                Paragraph(f"<b>Contact</b><br/>{escape(contact)}", value_style),
            ]],
            colWidths=["33%", "33%", "34%"],
        ),
        Spacer(1, 6),
    ]

    sections: dict[str, list[dict]] = {}
    for f in fields:
        if not f.get("active", True):
            continue
        sections.setdefault(f.get("section") or "Overview", []).append(f)

    for section_name, section_fields in sections.items():
        story.append(Paragraph(escape(section_name), section_style))
        rows = [
            [Paragraph(escape(f.get("label", f.get("key", ""))), label_style), Paragraph(escape(_pdf_field_value(doc, f)), value_style)]
            for f in section_fields
        ]
        table = Table(rows, colWidths=["35%", "65%"])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(table)

    if doc.custom_fields:
        known_keys = {f.get("key") for f in fields}
        extra = {k: v for k, v in doc.custom_fields.items() if k not in known_keys}
        if extra:
            story.append(Paragraph("Additional Fields", section_style))
            rows = [
                [Paragraph(escape(k.replace("_", " ")), label_style), Paragraph(escape(str(v) if v not in (None, "") else "—"), value_style)]
                for k, v in extra.items()
            ]
            table = Table(rows, colWidths=["35%", "65%"])
            table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
            ]))
            story.append(table)

    story.append(Spacer(1, 16))
    story.append(Paragraph("This document was generated by GenSmile Documents.", meta_style))

    pdf.build(story)
    return buffer.getvalue()


async def _package_document(db: AsyncSession, doc: PatientDocument) -> tuple[bytes, str, str]:
    """
    Build the downloadable package for a document: just the generated form
    PDF when there are no attached files, otherwise a zip of the attachments
    plus that PDF. Returns (content_bytes, filename, media_type).

    Zipped server-side rather than in the browser: the frontend used to
    `fetch()` each file's presigned S3 URL and zip them client-side, which
    silently produced an empty zip whenever the bucket's CORS policy blocked
    the cross-origin fetch (the failure was swallowed per-file). Downloading
    through our own API avoids the cross-origin S3 fetch entirely.
    """
    fields = await _resolve_form_fields(db, doc)
    safe_name = doc.patient_name.replace("/", "-") or "patient"

    # PDF rendering is a bonus on top of the attachments, not the reason the
    # download exists -- a reportlab failure (bad field data, missing dep on
    # a not-yet-redeployed server, etc.) shouldn't take down the ability to
    # get the files the doctor actually attached.
    try:
        pdf_bytes = _build_patient_document_pdf(doc, fields)
    except Exception as e:
        print(f"[PatientDocument] Form PDF generation failed for {doc.id}: {e}")
        pdf_bytes = None

    if not doc.files:
        if pdf_bytes is None:
            raise RuntimeError("PDF generation failed and there are no attached files to fall back to")
        return pdf_bytes, f"{safe_name}_form.pdf", "application/pdf"

    # Two entries with the same name (e.g. an attachment that happens to be
    # named the same as the generated form PDF) is valid per the zip spec,
    # but extracting to a real folder means writing two different files to
    # the same path -- several mobile file managers abort the whole
    # extraction on that conflict instead of overwriting or renaming.
    used_names: set[str] = set()

    def unique_name(name: str) -> str:
        if name not in used_names:
            used_names.add(name)
            return name
        stem, dot, ext = name.rpartition(".")
        base = stem if dot else name
        suffix = f".{ext}" if dot else ""
        for i in range(2, 1000):
            candidate = f"{base} ({i}){suffix}"
            if candidate not in used_names:
                used_names.add(candidate)
                return candidate
        return name  # extremely unlikely to be reached

    buffer = io.BytesIO()
    entries_written = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in doc.files:
            data = await s3_service.download_file_bytes(f.file_key)
            if data is not None:
                zf.writestr(unique_name(f.file_name), data)
                entries_written += 1
            else:
                print(f"[PatientDocument] Skipping attachment {f.file_name!r} ({f.file_key!r}) for {doc.id} -- S3 fetch failed")
        if pdf_bytes is not None:
            zf.writestr(unique_name(f"{safe_name}_form.pdf"), pdf_bytes)
            entries_written += 1

    # Every attachment's S3 fetch failed AND the PDF failed -- returning the
    # resulting zero-entry zip "succeeds" but silently hands the doctor an
    # empty archive with no indication anything went wrong. Fail loudly
    # instead so the frontend can show a real error.
    if entries_written == 0:
        raise RuntimeError(
            f"Could not retrieve any files for document {doc.id}: "
            f"{len(doc.files)} attachment(s) all failed to download from S3, and PDF generation failed."
        )

    return buffer.getvalue(), f"{safe_name}_documents.zip", "application/zip"


async def build_patient_document_zip(
    db: AsyncSession, user: UserAccount, document_id: UUID
) -> tuple[bytes, str, str] | None:
    """Doctor-authenticated: package for a document on the doctor's own account."""
    doc = await _get_owned_document(db, user, document_id)
    if not doc:
        return None
    return await _package_document(db, doc)


async def build_patient_fill_document_zip(
    db: AsyncSession, fill_token: str
) -> tuple[bytes, str, str] | None:
    """Public: same package, for the patient viewing their own self-fill
    form link (no doctor auth available on that page)."""
    doc = await _get_fill_enabled_document(db, fill_token)
    if not doc:
        return None
    return await _package_document(db, doc)


async def build_patient_document_public_zip(
    db: AsyncSession, share_token: str
) -> tuple[bytes, str, str] | None:
    """Public: same package, for another doctor viewing a doctor-to-doctor
    share link (no auth available on that page either)."""
    stmt = select(PatientDocument).where(
        PatientDocument.share_token == share_token,
        PatientDocument.is_shared.is_(True),
        PatientDocument.is_active.is_(True),
    )
    doc = await db.scalar(stmt)
    if not doc:
        return None
    return await _package_document(db, doc)


async def update_patient_document(
    db: AsyncSession, user: UserAccount, document_id: UUID, payload: PatientDocumentUpdate
) -> PatientDocumentRead | None:
    doc = await _get_owned_document(db, user, document_id)
    if not doc:
        return None

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(doc, field, value)

    # The doc form's phone/name/email fields are separate, denormalized
    # copies of the roster patient's own UserAccount/PatientProfile (which
    # the Patient List and Patient Details page read) -- a doctor editing
    # them here, after creating the patient from just a name, otherwise
    # never reaches the roster.
    roster_changed = False
    if doc.patient_user_id is not None:
        if "patient_phone" in updates:
            profile = await db.scalar(
                select(PatientProfile).where(PatientProfile.user_id == doc.patient_user_id)
            )
            if profile is not None:
                profile.phone = updates["patient_phone"]
                roster_changed = True

        if "patient_name" in updates or "patient_email" in updates:
            patient_user = await db.scalar(
                select(UserAccount).where(UserAccount.id == doc.patient_user_id)
            )
            if patient_user is not None:
                if "patient_name" in updates and updates["patient_name"].strip():
                    patient_user.full_name = updates["patient_name"].strip()
                    roster_changed = True

                if "patient_email" in updates:
                    new_email = (updates["patient_email"] or "").strip().lower()
                    if new_email and new_email != patient_user.email:
                        conflict = await db.scalar(
                            select(UserAccount).where(
                                UserAccount.email == new_email,
                                UserAccount.id != patient_user.id,
                            )
                        )
                        # Skip silently on a conflict (email already taken by
                        # another account) rather than failing the whole save
                        # -- the document's own copy still gets the new value.
                        if conflict is None:
                            patient_user.email = new_email
                            roster_changed = True

    await emit_event(db, doc.doctor_profile_id, {"type": "document_updated", "document_id": str(doc.id)})
    if roster_changed:
        # The Patient List / Patient Details page reads the roster, not this
        # document -- without this they'd never learn this write touched them.
        await emit_event(db, doc.doctor_profile_id, {"type": "patients_updated"})
    await db.commit()
    await db.refresh(doc)
    return _document_read(doc)


async def delete_patient_document(db: AsyncSession, user: UserAccount, document_id: UUID) -> bool:
    doc = await _get_owned_document(db, user, document_id)
    if not doc:
        return False

    for f in doc.files:
        await s3_service.delete_file_from_s3(f.file_key)
    if doc.logo_key:
        await s3_service.delete_file_from_s3(doc.logo_key)

    doctor_profile_id, document_id = doc.doctor_profile_id, doc.id
    await db.delete(doc)
    await emit_event(db, doctor_profile_id, {"type": "document_updated", "document_id": str(document_id), "deleted": True})
    await db.commit()
    return True


async def upload_document_logo(
    db: AsyncSession, user: UserAccount, document_id: UUID, file: UploadFile
) -> LogoUploadResponse | None:
    doc = await _get_owned_document(db, user, document_id)
    if not doc:
        return None

    key, _content_type, _size = await s3_service.upload_file_to_s3(
        file, prefix="logos", allowed_types=s3_service.ALLOWED_LOGO_TYPES
    )

    old_key = doc.logo_key
    doc.logo_key = key
    await emit_event(db, doc.doctor_profile_id, {"type": "document_updated", "document_id": str(doc.id)})
    await db.commit()

    if old_key:
        await s3_service.delete_file_from_s3(old_key)

    return LogoUploadResponse(logo_url=s3_service.get_presigned_url(key))


async def upload_document_file(
    db: AsyncSession, user: UserAccount, document_id: UUID, file: UploadFile
) -> PatientDocumentFileRead | None:
    doc = await _get_owned_document(db, user, document_id)
    if not doc:
        return None

    key, content_type, size = await s3_service.upload_file_to_s3(
        file, prefix="documents", allowed_types=None  # Allow all file types
    )
    file_type = s3_service.get_file_type_category(content_type, file.filename)

    doc_file = PatientDocumentFile(
        document_id=doc.id,
        file_name=file.filename or "file",
        file_key=key,
        file_type=file_type,
        file_size=size,
        uploaded_by=user.id,
        uploaded_by_patient=False,
    )
    db.add(doc_file)
    await emit_event(db, doc.doctor_profile_id, {"type": "document_updated", "document_id": str(doc.id)})
    await db.commit()
    await db.refresh(doc_file)
    return _file_read(doc_file)


async def delete_document_file(db: AsyncSession, user: UserAccount, file_id: UUID) -> bool:
    profile = await _require_doctor(db, user)
    stmt = (
        select(PatientDocumentFile)
        .join(PatientDocument, PatientDocumentFile.document_id == PatientDocument.id)
        .where(
            PatientDocumentFile.id == file_id,
            PatientDocument.doctor_profile_id == profile.id,
        )
    )
    doc_file = await db.scalar(stmt)
    if not doc_file:
        return False

    await s3_service.delete_file_from_s3(doc_file.file_key)
    document_id = doc_file.document_id
    await db.delete(doc_file)
    await emit_event(db, profile.id, {"type": "document_updated", "document_id": str(document_id)})
    await db.commit()
    return True


async def toggle_document_sharing(
    db: AsyncSession, user: UserAccount, document_id: UUID, is_shared: bool
) -> PatientDocumentRead | None:
    doc = await _get_owned_document(db, user, document_id)
    if not doc:
        return None

    doc.is_shared = is_shared
    if is_shared:
        doc.share_token = _new_token()

    await emit_event(db, doc.doctor_profile_id, {"type": "document_updated", "document_id": str(doc.id)})
    await db.commit()
    await db.refresh(doc)
    return _document_read(doc)


async def toggle_fill_enabled(
    db: AsyncSession, user: UserAccount, document_id: UUID, fill_enabled: bool
) -> PatientDocumentRead | None:
    doc = await _get_owned_document(db, user, document_id)
    if not doc:
        return None

    doc.fill_enabled = fill_enabled
    await emit_event(db, doc.doctor_profile_id, {"type": "document_updated", "document_id": str(doc.id)})
    await db.commit()
    await db.refresh(doc)
    return _document_read(doc)


# ─── Document-specific form config ─────────────────────────────────────────

async def get_document_form_config(
    db: AsyncSession, user: UserAccount, document_id: UUID
) -> list[dict] | None:
    """Get form config for a specific document. Falls back to doctor's default."""
    doc = await _get_owned_document(db, user, document_id)
    if not doc:
        return None

    if doc.form_config is not None:
        return doc.form_config

    # Fallback to doctor's default config
    try:
        config = await get_or_create_form_config_for_doctor(db, doc.doctor_profile_id)
        return config.fields if config else []
    except Exception:
        return []


async def update_document_form_config(
    db: AsyncSession, user: UserAccount, document_id: UUID, fields: list[dict]
) -> list[dict] | None:
    """Update form config for a specific document."""
    doc = await _get_owned_document(db, user, document_id)
    if not doc:
        return None

    doc.form_config = fields
    await emit_event(db, doc.doctor_profile_id, {"type": "document_updated", "document_id": str(doc.id)})
    await db.commit()
    await db.refresh(doc)
    return doc.form_config


async def get_patient_document_public_doctor(
    db: AsyncSession, share_token: str
) -> PatientDocumentPublicRead | None:
    stmt = select(PatientDocument).where(
        PatientDocument.share_token == share_token,
        PatientDocument.is_shared.is_(True),
        PatientDocument.is_active.is_(True),
    )
    doc = await db.scalar(stmt)
    if not doc:
        return None

    editable_fields, values = await _resolve_fields_and_values(db, doc)

    return PatientDocumentPublicRead(
        patient_name=doc.patient_name,
        patient_email=doc.patient_email,
        patient_phone=doc.patient_phone,
        doctor_name=_doctor_display_name(doc),
        logo_url=s3_service.get_presigned_url(doc.logo_key),
        visit_date=doc.visit_date,
        shared_at=doc.updated_at,
        fields=editable_fields,
        values=values,
        files=[_file_read(f) for f in doc.files],
    )


async def _resolve_fields_and_values(db: AsyncSession, doc: PatientDocument) -> tuple[list[dict], dict]:
    """Shared by the patient self-fill view and the doctor-to-doctor view --
    both render the same document's form fields/values, just one editable
    and one read-only."""
    # Use document-specific config, fallback to doctor's default
    if doc.form_config is not None:
        config_fields = doc.form_config
    else:
        try:
            config = await get_or_create_form_config_for_doctor(db, doc.doctor_profile_id)
            config_fields = config.fields if config else []
        except Exception:
            config_fields = []

    editable_fields = [f for f in config_fields if f.get("active")]

    values: dict = {}
    for f in editable_fields:
        key = f["key"]
        values[key] = getattr(doc, key, None) if f.get("core") else (doc.custom_fields or {}).get(key)

    # Include email and phone in values even if not in editable fields
    if "patient_email" not in values:
        values["patient_email"] = doc.patient_email
    if "patient_phone" not in values:
        values["patient_phone"] = doc.patient_phone
    if "patient_name" not in values:
        values["patient_name"] = doc.patient_name

    return editable_fields, values


async def get_patient_fill_document(
    db: AsyncSession, fill_token: str
) -> PatientFillFormRead | None:
    stmt = select(PatientDocument).where(
        PatientDocument.fill_token == fill_token,
        PatientDocument.fill_enabled.is_(True),
        PatientDocument.is_active.is_(True),
    )
    doc = await db.scalar(stmt)
    if not doc:
        return None

    editable_fields, values = await _resolve_fields_and_values(db, doc)

    return PatientFillFormRead(
        id=doc.id,
        patient_name=doc.patient_name,
        patient_email=doc.patient_email,  # ADD THIS
        patient_phone=doc.patient_phone,  # ADD THIS
        doctor_name=_doctor_display_name(doc),
        logo_url=s3_service.get_presigned_url(doc.logo_key),
        fields=editable_fields,
        values=values,
        submitted=doc.patient_submitted_at is not None,
        files=[_file_read(f) for f in doc.files],
    )


async def _get_fill_enabled_document(db: AsyncSession, fill_token: str) -> PatientDocument | None:
    stmt = select(PatientDocument).where(
        PatientDocument.fill_token == fill_token,
        PatientDocument.fill_enabled.is_(True),
        PatientDocument.is_active.is_(True),
    )
    return await db.scalar(stmt)


async def resolve_document_id_by_fill_token(db: AsyncSession, fill_token: str) -> UUID | None:
    """Used to authenticate the patient fill-in page's live-updates
    WebSocket -- the fill_token in the link IS the credential, same as
    every other public fill-in route."""
    doc = await _get_fill_enabled_document(db, fill_token)
    return doc.id if doc else None


async def resolve_document_id_by_share_token(db: AsyncSession, share_token: str) -> UUID | None:
    """Used to authenticate the doctor-to-doctor share page's live-updates
    WebSocket -- the share_token in the link IS the credential, same as
    every other public share-view route."""
    stmt = select(PatientDocument.id).where(
        PatientDocument.share_token == share_token,
        PatientDocument.is_shared.is_(True),
        PatientDocument.is_active.is_(True),
    )
    return await db.scalar(stmt)


async def resolve_documents_profile_id(db: AsyncSession, user: UserAccount) -> UUID:
    """The doctor profile whose documents this user sees (their own, or their
    doctor's for staff). Same role and staff-permission checks as every
    doctor-side documents route."""
    return (await _require_doctor(db, user)).id


async def upload_patient_fill_file(
    db: AsyncSession, fill_token: str, file: UploadFile
) -> PatientDocumentFileRead | None:
    """Public: the patient attaches a file (ID, insurance card, photo, etc.)
    to their own self-fill form before submitting."""
    doc = await _get_fill_enabled_document(db, fill_token)
    if not doc:
        return None

    key, content_type, size = await s3_service.upload_file_to_s3(
        file, prefix="documents", allowed_types=None  # Allow all file types
    )
    file_type = s3_service.get_file_type_category(content_type, file.filename)

    doc_file = PatientDocumentFile(
        document_id=doc.id,
        file_name=file.filename or "file",
        file_key=key,
        file_type=file_type,
        file_size=size,
        uploaded_by=None,
        uploaded_by_patient=True,
    )
    db.add(doc_file)
    await emit_event(db, doc.doctor_profile_id, {"type": "document_updated", "document_id": str(doc.id)})
    await db.commit()
    await db.refresh(doc_file)
    return _file_read(doc_file)


async def delete_patient_fill_file(db: AsyncSession, fill_token: str, file_id: UUID) -> bool:
    """Public: the patient removes a file they uploaded to their own
    self-fill form before submitting."""
    doc = await _get_fill_enabled_document(db, fill_token)
    if not doc:
        return False

    stmt = select(PatientDocumentFile).where(
        PatientDocumentFile.id == file_id,
        PatientDocumentFile.document_id == doc.id,
        PatientDocumentFile.uploaded_by_patient.is_(True),
    )
    doc_file = await db.scalar(stmt)
    if not doc_file:
        return False

    await s3_service.delete_file_from_s3(doc_file.file_key)
    await db.delete(doc_file)
    await emit_event(db, doc.doctor_profile_id, {"type": "document_updated", "document_id": str(doc.id)})
    await db.commit()
    return True

async def submit_patient_fill_document(
    db: AsyncSession, fill_token: str, payload: PatientFillFormSubmit
) -> PatientFillFormRead | None:
    stmt = select(PatientDocument).where(
        PatientDocument.fill_token == fill_token,
        PatientDocument.fill_enabled.is_(True),
        PatientDocument.is_active.is_(True),
    )
    doc = await db.scalar(stmt)
    if not doc:
        return None

    # Use document-specific config, fallback to doctor's default
    if doc.form_config is not None:
        config_fields = doc.form_config
    else:
        try:
            config = await get_or_create_form_config_for_doctor(db, doc.doctor_profile_id)
            config_fields = config.fields if config else []
        except Exception:
            config_fields = []

    editable_by_key = {f["key"]: f for f in config_fields if f.get("active")}

    custom_fields = dict(doc.custom_fields or {})
    for key, value in payload.values.items():
        field = editable_by_key.get(key)
        if not field:
            continue
        if field.get("core"):
            setattr(doc, key, value)
        else:
            custom_fields[key] = value
    doc.custom_fields = custom_fields

    if payload.patient_name:
        doc.patient_name = payload.patient_name
    if payload.patient_email:
        doc.patient_email = payload.patient_email
    if payload.patient_phone:
        doc.patient_phone = payload.patient_phone

    doc.patient_submitted_at = utc_now()

    await emit_event(db, doc.doctor_profile_id, {"type": "document_updated", "document_id": str(doc.id)})
    await db.commit()
    await db.refresh(doc)

    return await get_patient_fill_document(db, fill_token)