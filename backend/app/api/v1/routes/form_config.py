from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db_session
from app.controllers.form_config_controller import (
    get_or_create_form_config,
    update_form_config,
)
from app.models import UserAccount
from app.schemas.form_config import FormConfigRead, FormConfigUpdate
from app.services import s3_service

router = APIRouter(tags=["form-config"])

_401 = {401: {"description": "Missing or invalid access token"}}
_403 = {403: {"description": "Doctor role required"}}


def _read(config) -> FormConfigRead:
    return FormConfigRead(
        doctor_profile_id=config.doctor_profile_id,
        fields=config.fields,
        logo_url=s3_service.get_presigned_url(config.logo_key),
    )


@router.get("/form-config", response_model=FormConfigRead, status_code=status.HTTP_200_OK, responses={**_401, **_403})
async def get_my_form_config(
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> FormConfigRead:
    try:
        config = await get_or_create_form_config(db, current_user)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return _read(config)


@router.put("/form-config", response_model=FormConfigRead, status_code=status.HTTP_200_OK, responses={**_401, **_403})
async def update_my_form_config(
    payload: FormConfigUpdate,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> FormConfigRead:
    try:
        config = await update_form_config(db, current_user, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _read(config)
