import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db_session
from app.controllers.patient_document_controller import (
    build_patient_document_public_zip,
    build_patient_document_zip,
    build_patient_fill_document_zip,
    create_patient_document,
    delete_document_file,
    delete_patient_document,
    delete_patient_fill_file,
    delete_shared_document_file,
    get_document_form_config,
    get_document_form_config_by_share_token,
    get_patient_document,
    get_patient_document_changes,
    get_patient_document_public_doctor,
    get_patient_fill_document,
    list_patient_documents,
    list_shared_with_me,
    resolve_document_id_by_fill_token,
    resolve_document_id_by_share_token,
    resolve_documents_profile_id,
    submit_patient_fill_document,
    toggle_document_sharing,
    toggle_fill_enabled,
    update_document_by_share_token,
    update_document_form_config,
    update_document_form_config_by_share_token,
    update_patient_document,
    upload_document_file,
    upload_document_logo,
    upload_patient_fill_file,
    upload_shared_document_file,
)
from app.core.security import decode_access_token
from app.db.session import async_session_factory
from app.models import UserAccount
from app.schemas.patient_document import (
    DocumentFormConfigUpdate,
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
from app.services.document_events import document_events

router = APIRouter(tags=["patient-documents"])

_401 = {401: {"description": "Missing or invalid access token"}}
_403 = {403: {"description": "Doctor role required"}}
_404 = {404: {"description": "Document not found"}}
_AUTH = {**_401, **_403}


# ─── Live updates ──────────────────────────────────────────────────────────

_WS_AUTH_TIMEOUT_SECONDS = 10


async def _close_quietly(websocket: WebSocket, code: int, reason: str = "") -> None:
    # The client may already be gone (e.g. it disconnected during auth).
    try:
        await websocket.close(code=code, reason=reason)
    except RuntimeError:
        pass


@router.websocket("/patient-documents/ws")
async def patient_documents_live_updates(websocket: WebSocket) -> None:
    """Pushes {"type": "document_updated", "document_id": ...} the moment a
    patient changes one of this doctor's documents through their fill-in link,
    so the Documents page refetches immediately.

    The client authenticates with its first message, {"type": "auth",
    "token": <access token>}, rather than a ?token= query parameter, which
    would end up in server and proxy access logs. Close codes: 4401 = missing,
    invalid or expired token (refresh and reconnect); 4403 = this account
    can't use Documents.
    """
    await websocket.accept()
    try:
        message = await asyncio.wait_for(websocket.receive_json(), timeout=_WS_AUTH_TIMEOUT_SECONDS)
        payload = decode_access_token(str(message.get("token", "")))
        if message.get("type") != "auth" or payload.get("type") != "access":
            raise ValueError("bad auth message")
        user_id = UUID(str(payload.get("sub")))
    except (asyncio.TimeoutError, WebSocketDisconnect):
        await _close_quietly(websocket, 4401)
        return
    except Exception:
        await _close_quietly(websocket, 4401, "Invalid or expired token.")
        return

    async with async_session_factory() as db:
        user = await db.scalar(select(UserAccount).where(UserAccount.id == user_id))
        if user is None or not user.is_active:
            await _close_quietly(websocket, 4401, "User not found.")
            return
        try:
            doctor_profile_id = await resolve_documents_profile_id(db, user)
        except HTTPException:
            await _close_quietly(websocket, 4403, "No access to Documents.")
            return

    document_events.add(doctor_profile_id, websocket)
    try:
        await websocket.send_json({"type": "ready"})
        while True:
            # Nothing to act on from the client -- receiving just keeps the
            # connection open and notices when it closes (clients may ping).
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        document_events.remove(doctor_profile_id, websocket)


# ─── Doctor-authenticated routes ───────────────────────────────────────────

@router.get("/patient-documents", response_model=list[PatientDocumentRead], status_code=status.HTTP_200_OK, responses=_AUTH)
async def list_my_patient_documents(
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[PatientDocumentRead]:
    return await list_patient_documents(db=db, user=current_user)


@router.get("/patient-documents/shared-with-me", response_model=list[SharedWithMeDocumentRead], status_code=status.HTTP_200_OK, responses=_AUTH)
async def list_documents_shared_with_me(
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[SharedWithMeDocumentRead]:
    """Documents other doctors shared with this doctor (opened via their link)."""
    return await list_shared_with_me(db=db, user=current_user)


@router.post("/patient-documents", response_model=PatientDocumentRead, status_code=status.HTTP_201_CREATED, responses=_AUTH)
async def create_my_patient_document(
    payload: PatientDocumentCreate,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PatientDocumentRead:
    try:
        return await create_patient_document(db=db, user=current_user, payload=payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/patient-documents/{document_id}", response_model=PatientDocumentRead, status_code=status.HTTP_200_OK, responses={**_AUTH, **_404})
async def get_my_patient_document(
    document_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PatientDocumentRead:
    document = await get_patient_document(db=db, user=current_user, document_id=document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/patient-documents/{document_id}/changes", response_model=list[PatientDocumentChangeLogRead], status_code=status.HTTP_200_OK, responses={**_AUTH, **_404})
async def get_my_patient_document_changes(
    document_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[PatientDocumentChangeLogRead]:
    changes = await get_patient_document_changes(db=db, user=current_user, document_id=document_id)
    if changes is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return changes


@router.patch("/patient-documents/{document_id}", response_model=PatientDocumentRead, status_code=status.HTTP_200_OK, responses={**_AUTH, **_404})
async def update_my_patient_document(
    document_id: UUID,
    payload: PatientDocumentUpdate,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PatientDocumentRead:
    document = await update_patient_document(
        db=db, user=current_user, document_id=document_id, payload=payload
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.delete("/patient-documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT, responses={**_AUTH, **_404})
async def delete_my_patient_document(
    document_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    deleted = await delete_patient_document(db=db, user=current_user, document_id=document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")


@router.get("/patient-documents/{document_id}/download-zip", responses={**_AUTH, **_404})
async def download_my_document_zip(
    document_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> StreamingResponse:
    try:
        result = await build_patient_document_zip(db=db, user=current_user, document_id=document_id)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Document not found")
    content_bytes, filename, media_type = result
    safe_filename = filename.replace('"', "")
    return StreamingResponse(
        iter([content_bytes]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )


@router.post("/patient-documents/{document_id}/logo", response_model=LogoUploadResponse, status_code=status.HTTP_200_OK, responses={**_AUTH, **_404})
async def upload_my_document_logo(
    document_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    file: UploadFile = File(...),
) -> LogoUploadResponse:
    try:
        result = await upload_document_logo(
            db=db, user=current_user, document_id=document_id, file=file
        )
        if not result:
            raise HTTPException(status_code=404, detail="Document not found")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/patient-documents/{document_id}/files", response_model=PatientDocumentFileRead, status_code=status.HTTP_201_CREATED, responses={**_AUTH, **_404})
async def upload_my_document_file(
    document_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    file: UploadFile = File(...),
) -> PatientDocumentFileRead:
    try:
        result = await upload_document_file(
            db=db, user=current_user, document_id=document_id, file=file
        )
        if not result:
            raise HTTPException(status_code=404, detail="Document not found")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.delete("/patient-documents/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT, responses={**_AUTH, **_404})
async def delete_my_document_file(
    file_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    deleted = await delete_document_file(db=db, user=current_user, file_id=file_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")


@router.patch("/patient-documents/{document_id}/share", response_model=PatientDocumentRead, status_code=status.HTTP_200_OK, responses={**_AUTH, **_404})
async def toggle_my_document_sharing(
    document_id: UUID,
    is_shared: bool,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PatientDocumentRead:
    """Doctor-to-doctor sharing: exposes attached FILES ONLY."""
    document = await toggle_document_sharing(
        db=db, user=current_user, document_id=document_id, is_shared=is_shared
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.patch("/patient-documents/{document_id}/fill-link", response_model=PatientDocumentRead, status_code=status.HTTP_200_OK, responses={**_AUTH, **_404})
async def toggle_my_document_fill_link(
    document_id: UUID,
    fill_enabled: bool,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PatientDocumentRead:
    """Enable/disable the no-auth patient self-fill link."""
    document = await toggle_fill_enabled(
        db=db, user=current_user, document_id=document_id, fill_enabled=fill_enabled
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


# ─── Document-specific form config routes ─────────────────────────────────

@router.get("/patient-documents/{document_id}/form-config", status_code=status.HTTP_200_OK, responses={**_AUTH, **_404})
async def get_document_form_config_route(
    document_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Get form config for a specific document."""
    config = await get_document_form_config(db=db, user=current_user, document_id=document_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"fields": config}


@router.put("/patient-documents/{document_id}/form-config", status_code=status.HTTP_200_OK, responses={**_AUTH, **_404})
async def update_document_form_config_route(
    document_id: UUID,
    payload: DocumentFormConfigUpdate,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Update form config for a specific document."""
    config = await update_document_form_config(
        db=db, user=current_user, document_id=document_id, fields=payload.fields
    )
    if config is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"fields": config}


# ─── Public routes (no auth) ───────────────────────────────────────────────
#
# The token in each link IS the credential (same as every other route here),
# so these WebSockets need no auth handshake -- unlike /patient-documents/ws,
# which is scoped to everything a doctor can see, each of these is scoped to
# the ONE document its token unlocks, via document_events.add_document (see
# DocumentEventsManager) -- a viewer never learns about the doctor's other
# documents changing. (The doctor-to-doctor page's own GET/PATCH/form-config
# routes DO require login -- see the "Doctor-to-doctor" section below -- only
# this live-update ping and the patient self-fill routes stay token-only.)

async def _serve_document_scoped_ws(websocket: WebSocket, document_id: UUID | None) -> None:
    await websocket.accept()
    if document_id is None:
        await _close_quietly(websocket, 4404, "Link no longer active.")
        return
    document_events.add_document(document_id, websocket)
    try:
        await websocket.send_json({"type": "ready"})
        while True:
            # Nothing to act on from the client -- receiving just keeps the
            # connection open and notices when it closes (clients may ping).
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        document_events.remove_document(document_id, websocket)


@router.websocket("/doctor-to-doctor/documents/{share_token}/ws")
async def doctor_to_doctor_document_live_updates(
    share_token: str,
    websocket: WebSocket,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Pushes {"type": "document_updated", ...} the moment the shared
    document changes, so another doctor viewing this read-only link sees it
    update live instead of needing to reload."""
    document_id = await resolve_document_id_by_share_token(db, share_token)
    await _serve_document_scoped_ws(websocket, document_id)


@router.websocket("/patient-document/{fill_token}/ws")
async def patient_fill_document_live_updates(
    fill_token: str,
    websocket: WebSocket,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Pushes {"type": "document_updated", ...} the moment the doctor's copy
    of this document changes, so a patient filling out the form (e.g. the
    doctor edits something, disables the link, or the patient submitted it
    from another tab) sees it update live instead of needing to reload."""
    document_id = await resolve_document_id_by_fill_token(db, fill_token)
    await _serve_document_scoped_ws(websocket, document_id)


# ─── Doctor-to-doctor (login required) ─────────────────────────────────────
#
# The share link is no longer anonymous: whoever opens it must sign in with a
# doctor or staff account (any such account, not just the document's owner --
# see _require_doctor) before they can view or edit the form. Every edit made
# here (or by the owner through their own dashboard) is written to this
# document's change log, which every doctor with the link can see.

@router.get(
    "/doctor-to-doctor/documents/{share_token}",
    response_model=PatientDocumentPublicRead,
    status_code=status.HTTP_200_OK,
    responses={**_AUTH, **_404},
)
async def get_doctor_to_doctor_document(
    share_token: str,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PatientDocumentPublicRead:
    """Doctor-authenticated: another doctor opens a doctor-to-doctor share
    link and signs in first."""
    document = await get_patient_document_public_doctor(db=db, user=current_user, share_token=share_token)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found or no longer available")
    return document


@router.patch(
    "/doctor-to-doctor/documents/{share_token}",
    response_model=PatientDocumentPublicRead,
    status_code=status.HTTP_200_OK,
    responses={**_AUTH, **_404},
)
async def update_doctor_to_doctor_document(
    share_token: str,
    payload: PatientDocumentUpdate,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PatientDocumentPublicRead:
    """Doctor-authenticated: edit the shared form's values. Logged to this
    document's change log under the signed-in doctor's name."""
    document = await update_document_by_share_token(db=db, user=current_user, share_token=share_token, payload=payload)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found or no longer available")
    return document


@router.post(
    "/doctor-to-doctor/documents/{share_token}/files",
    response_model=PatientDocumentFileRead,
    status_code=status.HTTP_201_CREATED,
    responses={**_AUTH, **_404},
)
async def upload_doctor_to_doctor_file_route(
    share_token: str,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    file: UploadFile = File(...),
) -> PatientDocumentFileRead:
    """Doctor-authenticated: attach a file to the shared document."""
    try:
        result = await upload_shared_document_file(db=db, user=current_user, share_token=share_token, file=file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Document not found or no longer available")
    return result


@router.delete(
    "/doctor-to-doctor/documents/{share_token}/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**_AUTH, **_404},
)
async def delete_doctor_to_doctor_file_route(
    share_token: str,
    file_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Doctor-authenticated: remove a file this doctor uploaded via the link."""
    if not await delete_shared_document_file(db=db, user=current_user, share_token=share_token, file_id=file_id):
        raise HTTPException(status_code=404, detail="File not found")


@router.get(
    "/doctor-to-doctor/documents/{share_token}/form-config",
    status_code=status.HTTP_200_OK,
    responses={**_AUTH, **_404},
)
async def get_doctor_to_doctor_form_config_route(
    share_token: str,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Doctor-authenticated: form config for the "Edit Form" settings modal."""
    config = await get_document_form_config_by_share_token(db=db, user=current_user, share_token=share_token)
    if config is None:
        raise HTTPException(status_code=404, detail="Document not found or no longer available")
    return {"fields": config}


@router.put(
    "/doctor-to-doctor/documents/{share_token}/form-config",
    status_code=status.HTTP_200_OK,
    responses={**_AUTH, **_404},
)
async def update_doctor_to_doctor_form_config_route(
    share_token: str,
    payload: DocumentFormConfigUpdate,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Doctor-authenticated: edit the shared form's field settings. Logged to
    this document's change log under the signed-in doctor's name."""
    config = await update_document_form_config_by_share_token(
        db=db, user=current_user, share_token=share_token, fields=payload.fields
    )
    if config is None:
        raise HTTPException(status_code=404, detail="Document not found or no longer available")
    return {"fields": config}


@router.get("/doctor-to-doctor/documents/{share_token}/download-zip", responses={**_AUTH, **_404})
async def download_doctor_to_doctor_zip_route(
    share_token: str,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> StreamingResponse:
    """Doctor-authenticated: another doctor downloads the form PDF +
    attached files (just the PDF, unzipped, when there are no attached
    files) from a doctor-to-doctor share link."""
    try:
        result = await build_patient_document_public_zip(db=db, share_token=share_token, user=current_user)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Document not found or no longer available")
    content_bytes, filename, media_type = result
    safe_filename = filename.replace('"', "")
    return StreamingResponse(
        iter([content_bytes]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )


@router.get(
    "/patient-document/{fill_token}",
    response_model=PatientFillFormRead,
    status_code=status.HTTP_200_OK,
    responses=_404,
)
async def get_patient_fill_form_route(
    fill_token: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PatientFillFormRead:
    """Public: patient opens their self-fill form link."""
    document = await get_patient_fill_document(db=db, fill_token=fill_token)
    if not document:
        raise HTTPException(status_code=404, detail="Form not found or no longer available")
    return document


@router.get("/patient-document/{fill_token}/download-zip", responses=_404)
async def download_patient_fill_zip_route(
    fill_token: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> StreamingResponse:
    """Public: patient downloads their own attached files + form PDF (just
    the PDF, unzipped, when there are no attached files)."""
    try:
        result = await build_patient_fill_document_zip(db=db, fill_token=fill_token)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Form not found or no longer available")
    content_bytes, filename, media_type = result
    safe_filename = filename.replace('"', "")
    return StreamingResponse(
        iter([content_bytes]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )


@router.post(
    "/patient-document/{fill_token}",
    response_model=PatientFillFormRead,
    status_code=status.HTTP_200_OK,
    responses=_404,
)
async def submit_patient_fill_form_route(
    fill_token: str,
    payload: PatientFillFormSubmit,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PatientFillFormRead:
    """Public: patient submits their filled-out form."""
    result = await submit_patient_fill_document(
        db=db, fill_token=fill_token, payload=payload
    )
    if not result:
        raise HTTPException(status_code=404, detail="Form not found or no longer available")
    return result


@router.post(
    "/patient-document/{fill_token}/files",
    response_model=PatientDocumentFileRead,
    status_code=status.HTTP_201_CREATED,
    responses=_404,
)
async def upload_patient_fill_file_route(
    fill_token: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    file: UploadFile = File(...),
) -> PatientDocumentFileRead:
    """Public: patient attaches a file to their own self-fill form."""
    try:
        result = await upload_patient_fill_file(db=db, fill_token=fill_token, file=file)
        if not result:
            raise HTTPException(status_code=404, detail="Form not found or no longer available")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return result


@router.delete(
    "/patient-document/{fill_token}/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_404,
)
async def delete_patient_fill_file_route(
    fill_token: str,
    file_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Public: patient removes a file they uploaded to their own self-fill form."""
    deleted = await delete_patient_fill_file(db=db, fill_token=fill_token, file_id=file_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")