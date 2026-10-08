import re
import copy
import logging
import secrets
import io
import os
import zipfile
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.controllers.form_config_controller import get_or_create_form_config_for_doctor
from app.services.document_events import emit_event
from app.models import DoctorPatient, DoctorProfile, PatientProfile, UserAccount, UserRole
from app.models.staff import StaffMember
from app.models.base import utc_now
from app.models.patient_document import PatientDocument, PatientDocumentChangeLog, PatientDocumentFile, PatientDocumentSharedAccess
from app.schemas.patient_document import (
    LogoUploadResponse,
    PatientDocumentChangeLogRead,
    PatientDocumentCreate,
    PatientDocumentFileRead,
    PatientDocumentPublicRead,
    PatientDocumentRead,
    PatientDocumentUpdate,
    PatientFillFormRead,
    PatientFillFormSubmit,
    SharedWithMeDocumentRead,
)
from app.services import s3_service

logger = logging.getLogger(__name__)

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


async def _doctor_display_name(db: AsyncSession, doc: PatientDocument) -> str:
    # The name lives on the doctor's UserAccount, not DoctorProfile. Empty
    # string lets the frontend show its own "Your Doctor" fallback.
    name = await db.scalar(
        select(UserAccount.full_name)
        .join(DoctorProfile, DoctorProfile.user_id == UserAccount.id)
        .where(DoctorProfile.id == doc.doctor_profile_id)
    )
    # Pages show "Dr. {name}" -- drop a "Dr." the doctor already typed into
    # their own name, or it reads "Dr. Dr. Nilo".
    return _without_dr(name)


def _without_dr(name: str | None) -> str:
    return re.sub(r"^\s*dr(\.\s*|\s+)", "", name or "", flags=re.IGNORECASE).strip()


def _file_read(f: PatientDocumentFile) -> PatientDocumentFileRead:
    return PatientDocumentFileRead(
        id=f.id,
        file_name=f.file_name,
        file_type=f.file_type,
        file_size=f.file_size,
        file_url=s3_service.get_presigned_url(f.file_key, download_filename=f.file_name),
        uploaded_by_patient=f.uploaded_by_patient,
        uploaded_by=f.uploaded_by,
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
    db: AsyncSession, user: UserAccount, document_id: UUID, for_update: bool = False
) -> PatientDocument | None:
    profile = await _require_doctor(db, user)
    stmt = select(PatientDocument).where(
        PatientDocument.id == document_id,
        PatientDocument.doctor_profile_id == profile.id,
    )
    if for_update:
        stmt = stmt.with_for_update()
    return await db.scalar(stmt)


async def _get_shared_document(db: AsyncSession, share_token: str, for_update: bool = False) -> PatientDocument | None:
    """Resolve a doctor-to-doctor share link's document -- NOT scoped to the
    caller owning it, since the whole point of this link is that a different
    doctor opens it. Authorization is instead "any authenticated doctor/staff
    account" (see _require_doctor), enforced separately by each caller.

    for_update=True locks the row (SELECT ... FOR UPDATE, on Postgres --
    SQLite has no row locking and silently ignores it, a pre-existing
    limitation of local dev shared with the rest of this codebase, e.g.
    document_events' pg_notify) for the duration of the caller's
    transaction. Pass it whenever the row is about to be read-modify-written
    (an edit, not a plain GET) -- with several doctors able to PATCH the same
    shared document at once, without this a second request's read can land
    between a first request's read and write and silently lose part of the
    first request's update once both commit.
    """
    stmt = select(PatientDocument).where(
        PatientDocument.share_token == share_token,
        PatientDocument.is_shared.is_(True),
        PatientDocument.is_active.is_(True),
    )
    if for_update:
        stmt = stmt.with_for_update()
    return await db.scalar(stmt)


# ─── Change log ─────────────────────────────────────────────────────────────

def _prettify_key(key: str) -> str:
    return key.replace("_", " ").strip().title()


def _stringify_value(value: object) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


async def _field_label_map(db: AsyncSession, doc: PatientDocument) -> dict[str, str]:
    fields = await _resolve_form_fields(db, doc)
    labels = {f["key"]: f.get("label") or f["key"] for f in fields}
    labels.setdefault("patient_name", "Patient Name")
    labels.setdefault("patient_email", "Email")
    labels.setdefault("patient_phone", "Phone")
    labels.setdefault("visit_date", "Visit Date")
    return labels


def _add_change_log(
    db: AsyncSession,
    document_id: UUID,
    actor: UserAccount | None,
    change_type: str,  # "value" | "settings" | "file" | "sharing" | "document"
    field_key: str | None,
    field_label: str,
    old_value: object,
    new_value: object,
) -> None:
    """actor=None means the patient themselves, via the no-auth self-fill link."""
    old_s, new_s = _stringify_value(old_value), _stringify_value(new_value)
    if old_s == new_s:
        return  # No actual change -- e.g. "" -> None -- nothing worth logging.
    db.add(PatientDocumentChangeLog(
        document_id=document_id,
        changed_by_user_id=actor.id if actor else None,
        changed_by_name=actor.full_name if actor else "Patient (self-fill link)",
        change_type=change_type,
        field_key=field_key,
        field_label=field_label,
        old_value=old_s,
        new_value=new_s,
    ))


async def _get_change_log(db: AsyncSession, document_id: UUID, limit: int = 200) -> list[PatientDocumentChangeLogRead]:
    stmt = (
        select(PatientDocumentChangeLog)
        .where(PatientDocumentChangeLog.document_id == document_id)
        .order_by(PatientDocumentChangeLog.created_at.desc())
        .limit(limit)
    )
    rows = (await db.scalars(stmt)).all()
    return [PatientDocumentChangeLogRead.model_validate(r) for r in rows]


# Which FieldConfig attributes are worth an audit entry when they change, and
# the human-readable name for each. `order` is deliberately excluded -- every
# add/delete/reorder shifts every other field's order number too, which would
# spam the log with noise that isn't really "information" changing.
_FIELD_SETTING_ASPECTS: list[tuple[str, str]] = [
    ("label", "Label"),
    ("section", "Section"),
    ("active", "Show on form"),
    ("patient_editable", "Patient can fill"),
    ("required", "Required"),
]


def _log_form_config_changes(
    db: AsyncSession,
    document_id: UUID,
    actor: UserAccount,
    old_fields: list[dict] | None,
    new_fields: list[dict],
) -> None:
    old_by_key = {f["key"]: f for f in (old_fields or [])}
    new_by_key = {f["key"]: f for f in new_fields}

    for key, new_f in new_by_key.items():
        label = new_f.get("label") or key
        old_f = old_by_key.get(key)
        if old_f is None:
            _add_change_log(db, document_id, actor, "settings", key, label, None, "Field added")
            continue
        for attr, aspect in _FIELD_SETTING_ASPECTS:
            _add_change_log(
                db, document_id, actor, "settings", key, f"{label} — {aspect}",
                old_f.get(attr), new_f.get(attr),
            )

    for key, old_f in old_by_key.items():
        if key not in new_by_key:
            _add_change_log(db, document_id, actor, "settings", key, old_f.get("label") or key, "Field removed", None)


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
    custom_form_config = data.pop("form_config", None)

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
        # Its own copy, so editing this form can never change the default or other forms.
        form_config=copy.deepcopy(custom_form_config or default_fields),
        **data,
    )
    db.add(doc)
    await db.flush()  # populate doc.id (client-side default) before it's used below
    _add_change_log(db, doc.id, user, "document", None, "Document", None, "Created")
    await emit_event(db, profile.id, {"type": "document_updated", "document_id": str(doc.id)})
    await db.commit()
    await db.refresh(doc)
    return _document_read(doc)


async def get_patient_document(
    db: AsyncSession, user: UserAccount, document_id: UUID
) -> PatientDocumentRead | None:
    doc = await _get_owned_document(db, user, document_id)
    return _document_read(doc) if doc else None


async def get_patient_document_changes(
    db: AsyncSession, user: UserAccount, document_id: UUID
) -> list[PatientDocumentChangeLogRead] | None:
    doc = await _get_owned_document(db, user, document_id)
    return await _get_change_log(db, doc.id) if doc else None


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
    db: AsyncSession, share_token: str, user: UserAccount
) -> tuple[bytes, str, str] | None:
    """Doctor-authenticated: another doctor downloading the form PDF + files
    from a doctor-to-doctor share link. Login is required here too now --
    this bundle can contain the same PHI as the page itself."""
    await _require_doctor(db, user)
    doc = await _get_shared_document(db, share_token)
    if not doc:
        return None
    return await _package_document(db, doc)


async def _apply_document_update(
    db: AsyncSession, doc: PatientDocument, actor: UserAccount, updates: dict
) -> bool:
    """Core mutation shared by the owner-authenticated update
    (update_patient_document) and the doctor-to-doctor share-link update
    (update_document_by_share_token): apply each changed field, write an
    audit-log entry per actual change, and sync the roster copy of
    patient_phone/name/email when this document is linked to a roster
    patient. Returns whether the roster was touched (callers use that to
    decide whether to also emit a patients_updated event)."""
    field_labels = await _field_label_map(db, doc)

    for field, value in updates.items():
        if field == "custom_fields":
            # Merge, never replace: doc.custom_fields holds every custom
            # field's value in one JSON blob, and the client only sends the
            # keys it actually touched (see the frontend's dirty-field
            # tracking). A concurrent editor's PATCH is a separate DB
            # transaction that already committed by the time this one reads
            # doc -- replacing the whole dict here would silently wipe out
            # whatever key(s) that other request just wrote. Ten doctors on
            # the same shared document editing different fields at once must
            # not be able to stomp on each other this way.
            old_dict = doc.custom_fields or {}
            incoming = value or {}
            for key, new_val in incoming.items():
                _add_change_log(
                    db, doc.id, actor, "value", key, field_labels.get(key, _prettify_key(key)),
                    old_dict.get(key), new_val,
                )
            setattr(doc, field, {**old_dict, **incoming})
            continue

        old_value = getattr(doc, field, None)
        _add_change_log(db, doc.id, actor, "value", field, field_labels.get(field, _prettify_key(field)), old_value, value)
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

    return roster_changed


async def _emit_document_update_events(db: AsyncSession, doc: PatientDocument, roster_changed: bool) -> None:
    await emit_event(db, doc.doctor_profile_id, {"type": "document_updated", "document_id": str(doc.id)})
    if roster_changed:
        # The Patient List / Patient Details page reads the roster, not this
        # document -- without this they'd never learn this write touched them.
        await emit_event(db, doc.doctor_profile_id, {"type": "patients_updated"})


async def update_patient_document(
    db: AsyncSession, user: UserAccount, document_id: UUID, payload: PatientDocumentUpdate
) -> PatientDocumentRead | None:
    # Locked: this document may also be getting PATCHed right now through a
    # doctor-to-doctor share link (a different doctor, a separate DB
    # transaction) -- without the lock, both transactions could read
    # custom_fields before either commits, and whichever commits last would
    # silently overwrite the other's merge.
    doc = await _get_owned_document(db, user, document_id, for_update=True)
    if not doc:
        return None

    updates = payload.model_dump(exclude_unset=True)
    roster_changed = await _apply_document_update(db, doc, user, updates)
    await _emit_document_update_events(db, doc, roster_changed)
    await db.commit()
    await db.refresh(doc)
    return _document_read(doc)


async def update_document_by_share_token(
    db: AsyncSession, user: UserAccount, share_token: str, payload: PatientDocumentUpdate
) -> PatientDocumentPublicRead | None:
    """Doctor-to-doctor: any authenticated doctor/staff account (not just the
    document's owner) edits the shared form. Returns the same shape the page
    already renders (values/fields/changes), never the owner-only
    PatientDocumentRead -- that would leak this document's share_token/
    fill_token to whoever else has this link."""
    await _require_doctor(db, user)
    # Locked: ten doctors could be PATCHing this same shared document right
    # now, each in their own transaction -- see update_patient_document.
    doc = await _get_shared_document(db, share_token, for_update=True)
    if not doc:
        return None

    updates = payload.model_dump(exclude_unset=True)
    roster_changed = await _apply_document_update(db, doc, user, updates)
    await _emit_document_update_events(db, doc, roster_changed)
    await db.commit()
    await db.refresh(doc)
    return await get_patient_document_public_doctor(db, user, share_token)


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
    _add_change_log(db, doc.id, user, "document", None, "Logo", "Replaced" if old_key else None, file.filename or "Uploaded")
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
    _add_change_log(db, doc.id, user, "file", None, "Attachment", None, f"Uploaded {doc_file.file_name}")
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
    _add_change_log(db, document_id, user, "file", None, "Attachment", doc_file.file_name, "Removed")
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

    _add_change_log(db, doc.id, user, "sharing", None, "Doctor-to-doctor link", doc.is_shared, is_shared)
    if is_shared and doc.is_shared:
        _add_change_log(db, doc.id, user, "sharing", None, "Doctor-to-doctor link", None, "New link generated")
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

    _add_change_log(db, doc.id, user, "sharing", None, "Patient self-fill link", doc.fill_enabled, fill_enabled)
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


async def _apply_form_config_update(
    db: AsyncSession, doc: PatientDocument, actor: UserAccount, fields: list[dict]
) -> None:
    old_fields = doc.form_config if doc.form_config is not None else await _resolve_form_fields(db, doc)
    _log_form_config_changes(db, doc.id, actor, old_fields, fields)
    doc.form_config = fields


async def update_document_form_config(
    db: AsyncSession, user: UserAccount, document_id: UUID, fields: list[dict]
) -> list[dict] | None:
    """Update form config for a specific document (the document's owner)."""
    doc = await _get_owned_document(db, user, document_id, for_update=True)
    if not doc:
        return None

    await _apply_form_config_update(db, doc, user, fields)
    await emit_event(db, doc.doctor_profile_id, {"type": "document_updated", "document_id": str(doc.id)})
    await db.commit()
    await db.refresh(doc)
    return doc.form_config


async def get_document_form_config_by_share_token(
    db: AsyncSession, user: UserAccount, share_token: str
) -> list[dict] | None:
    """Doctor-to-doctor: form config for the "Edit Form" settings modal,
    opened by any authenticated doctor/staff account."""
    await _require_doctor(db, user)
    doc = await _get_shared_document(db, share_token)
    if not doc:
        return None
    if doc.form_config is not None:
        return doc.form_config
    return await _resolve_form_fields(db, doc)


async def update_document_form_config_by_share_token(
    db: AsyncSession, user: UserAccount, share_token: str, fields: list[dict]
) -> list[dict] | None:
    """Doctor-to-doctor: any authenticated doctor/staff account changes this
    document's form settings. Unlike the owner's own edit, this never pushes
    to the owner's doctor-wide default template -- a visiting doctor has no
    default template of their own to update."""
    await _require_doctor(db, user)
    doc = await _get_shared_document(db, share_token, for_update=True)
    if not doc:
        return None

    await _apply_form_config_update(db, doc, user, fields)
    await emit_event(db, doc.doctor_profile_id, {"type": "document_updated", "document_id": str(doc.id)})
    await db.commit()
    await db.refresh(doc)
    return doc.form_config


async def _record_shared_access(db: AsyncSession, doc: PatientDocument, user: UserAccount) -> None:
    """Remember that this doctor opened this share link, for their Shared
    Documents list. The page re-fetches on every live update, so only write
    when something actually changed (new link, or >5 min since last time)."""
    access = await db.scalar(select(PatientDocumentSharedAccess).where(
        PatientDocumentSharedAccess.document_id == doc.id,
        PatientDocumentSharedAccess.user_id == user.id,
    ))
    now = utc_now()
    if access is not None and access.share_token == doc.share_token and (now - access.last_opened_at).total_seconds() <= 300:
        return
    try:
        # Savepoint: if two tabs insert at the same instant, only this row is
        # rolled back -- not the document the caller is about to read.
        async with db.begin_nested():
            if access is None:
                db.add(PatientDocumentSharedAccess(document_id=doc.id, user_id=user.id, share_token=doc.share_token, last_opened_at=now))
            else:
                access.share_token, access.last_opened_at = doc.share_token, now
    except IntegrityError:
        return
    except SQLAlchemyError:
        # Never let bookkeeping break opening the document itself.
        logger.exception("Couldn't record shared-document access")
        return
    await db.commit()


async def list_shared_with_me(db: AsyncSession, user: UserAccount) -> list[SharedWithMeDocumentRead]:
    profile = await _require_doctor(db, user)
    stmt = (
        select(PatientDocument, PatientDocumentSharedAccess.last_opened_at, UserAccount.full_name)
        .join(PatientDocumentSharedAccess, PatientDocumentSharedAccess.document_id == PatientDocument.id)
        .join(DoctorProfile, DoctorProfile.id == PatientDocument.doctor_profile_id)
        .join(UserAccount, UserAccount.id == DoctorProfile.user_id)
        .where(
            PatientDocumentSharedAccess.user_id == user.id,
            # Still the link they were given, and still shared.
            PatientDocumentSharedAccess.share_token == PatientDocument.share_token,
            PatientDocument.is_shared.is_(True),
            PatientDocument.is_active.is_(True),
            PatientDocument.doctor_profile_id != profile.id,
        )
        .order_by(PatientDocumentSharedAccess.last_opened_at.desc())
    )
    return [
        SharedWithMeDocumentRead(
            share_token=doc.share_token,
            patient_name=doc.patient_name,
            owner_name=_without_dr(owner_name) or "Unknown doctor",
            logo_url=s3_service.get_presigned_url(doc.logo_key),
            visit_date=doc.visit_date,
            updated_at=doc.updated_at,
            last_opened_at=last_opened_at,
        )
        for doc, last_opened_at, owner_name in (await db.execute(stmt)).all()
    ]


async def get_patient_document_public_doctor(
    db: AsyncSession, user: UserAccount, share_token: str
) -> PatientDocumentPublicRead | None:
    """Doctor-to-doctor: any authenticated doctor/staff account opens the
    share link and logs in first -- see _require_doctor. No longer anonymous."""
    profile = await _require_doctor(db, user)
    doc = await _get_shared_document(db, share_token)
    if not doc:
        return None
    if doc.doctor_profile_id != profile.id:
        await _record_shared_access(db, doc, user)

    editable_fields, values = await _resolve_fields_and_values(db, doc)
    changes = await _get_change_log(db, doc.id)

    return PatientDocumentPublicRead(
        patient_name=doc.patient_name,
        patient_email=doc.patient_email,
        patient_phone=doc.patient_phone,
        doctor_name=await _doctor_display_name(db, doc),
        logo_url=s3_service.get_presigned_url(doc.logo_key),
        visit_date=doc.visit_date,
        shared_at=doc.updated_at,
        changes=changes,
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
        visit_date=doc.visit_date,
        doctor_name=await _doctor_display_name(db, doc),
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


async def upload_shared_document_file(
    db: AsyncSession, user: UserAccount, share_token: str, file: UploadFile
) -> PatientDocumentFileRead | None:
    """Doctor-to-doctor: any authenticated doctor/staff account with the link
    attaches a file. Logged under their name, like their field edits."""
    await _require_doctor(db, user)
    doc = await _get_shared_document(db, share_token)
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
    _add_change_log(db, doc.id, user, "file", None, "Attachment", None, f"Uploaded {doc_file.file_name}")
    await emit_event(db, doc.doctor_profile_id, {"type": "document_updated", "document_id": str(doc.id)})
    await db.commit()
    await db.refresh(doc_file)
    return _file_read(doc_file)


async def delete_shared_document_file(db: AsyncSession, user: UserAccount, share_token: str, file_id: UUID) -> bool:
    """Doctor-to-doctor: a doctor removes a file THEY uploaded through the
    link -- never the owner's or the patient's files."""
    await _require_doctor(db, user)
    doc = await _get_shared_document(db, share_token)
    if not doc:
        return False

    stmt = select(PatientDocumentFile).where(
        PatientDocumentFile.id == file_id,
        PatientDocumentFile.document_id == doc.id,
        PatientDocumentFile.uploaded_by == user.id,
    )
    doc_file = await db.scalar(stmt)
    if not doc_file:
        return False

    await s3_service.delete_file_from_s3(doc_file.file_key)
    _add_change_log(db, doc.id, user, "file", None, "Attachment", doc_file.file_name, "Removed")
    await db.delete(doc_file)
    await emit_event(db, doc.doctor_profile_id, {"type": "document_updated", "document_id": str(doc.id)})
    await db.commit()
    return True


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
    _add_change_log(db, doc.id, None, "file", None, "Attachment", None, f"Uploaded {doc_file.file_name}")
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
    _add_change_log(db, doc.id, None, "file", None, "Attachment", doc_file.file_name, "Removed")
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
        label = field.get("label") or _prettify_key(key)
        if field.get("core"):
            _add_change_log(db, doc.id, None, "value", key, label, getattr(doc, key, None), value)
            setattr(doc, key, value)
        else:
            _add_change_log(db, doc.id, None, "value", key, label, custom_fields.get(key), value)
            custom_fields[key] = value
    doc.custom_fields = custom_fields

    for attr, label in (("patient_name", "Patient Name"), ("patient_email", "Email"), ("patient_phone", "Phone")):
        new_val = getattr(payload, attr)
        if new_val:
            _add_change_log(db, doc.id, None, "value", attr, label, getattr(doc, attr), new_val)
            setattr(doc, attr, new_val)
    if payload.visit_date is not None:
        _add_change_log(db, doc.id, None, "value", "visit_date", "Visit Date", doc.visit_date, payload.visit_date)
        doc.visit_date = payload.visit_date

    doc.patient_submitted_at = utc_now()

    await emit_event(db, doc.doctor_profile_id, {"type": "document_updated", "document_id": str(doc.id)})
    await db.commit()
    await db.refresh(doc)

    return await get_patient_fill_document(db, fill_token)