"""The two endpoints the Documents app needs from outside the documents and
auth routers, carried over unchanged from the full GenSmile API:

- GET /doctors/patients -- the doctor's patient list, for the "Existing
  patient" picker on the Documents page.
- GET /staff/me -- a staff user's own record, which holds the permissions
  the frontend checks (e.g. patient_documents).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db_session
from app.controllers.doctor_patient_controller import list_doctor_patients
from app.core.pagination import PaginatedResponse, PaginationParams
from app.models import StaffMember, UserAccount
from app.models.enums import DoctorPatientStatus, UserRole
from app.schemas.doctor import DoctorPatientRead
from app.schemas.staff import StaffMemberRead

router = APIRouter()

_401 = {401: {"description": "Missing or invalid access token"}}
_403 = {403: {"description": "Doctor role required"}}
_AUTH = {**_401, **_403}


@router.get(
    "/doctors/patients",
    response_model=PaginatedResponse[DoctorPatientRead],
    status_code=status.HTTP_200_OK,
    summary="List my patients",
    description=(
        "Return a paginated list of patients linked to the authenticated doctor. "
        "Optionally filter by partial name or email with the `query` parameter."
    ),
    responses=_AUTH,
    tags=["doctors"],
)
async def get_patients(
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    params: Annotated[PaginationParams, Depends()],
    query: str | None = Query(default=None, max_length=100, description="Filter by name or email"),
    status: DoctorPatientStatus | None = Query(default=None, description="Filter by status (pending, active, inactive)"),
) -> PaginatedResponse[DoctorPatientRead]:
    items, total = await list_doctor_patients(
        db=db,
        user=current_user,
        query=query,
        status_filter=status,
        page=params.page,
        page_size=params.page_size,
    )
    return PaginatedResponse.build(items=items, total=total, params=params)


@router.get(
    "/staff/me",
    response_model=StaffMemberRead,
    status_code=status.HTTP_200_OK,
    summary="Get my staff member record",
    description=(
        "Returns the staff member record for the currently logged-in staff user, "
        "including their permissions. This endpoint is for STAFF role only."
    ),
    responses=_401,
    tags=["staff"],
)
async def get_my_staff_record(
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> StaffMemberRead:
    if current_user.role != UserRole.STAFF:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff role required.")
    member = await db.scalar(
        select(StaffMember).where(
            StaffMember.user_id == current_user.id,
            StaffMember.is_active.is_(True),
        )
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff record not found.")
    return StaffMemberRead.model_validate(member)
