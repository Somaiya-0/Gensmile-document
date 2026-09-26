import re
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

FIELD_TYPES = {"text", "textarea", "checkbox", "date", "select"}

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


class FieldConfig(BaseModel):
    key: str
    label: str = Field(min_length=1, max_length=200)
    type: str = "text"
    section: str = Field(min_length=1, max_length=120)
    order: int = 0
    active: bool = True
    required: bool = False
    patient_editable: bool = False
    core: bool = False
    options: list[str] | None = None  # only used when type == "select"

    @field_validator("type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in FIELD_TYPES:
            raise ValueError(f"type must be one of {sorted(FIELD_TYPES)}")
        return v

    @field_validator("key")
    @classmethod
    def _valid_key(cls, v: str) -> str:
        if not _KEY_RE.match(v):
            raise ValueError(
                "key must be lowercase, start with a letter, and contain only "
                "letters, numbers, or underscores"
            )
        return v


class FormConfigRead(BaseModel):
    doctor_profile_id: UUID
    fields: list[FieldConfig]
    logo_url: str | None = None


class FormConfigUpdate(BaseModel):
    fields: list[FieldConfig]