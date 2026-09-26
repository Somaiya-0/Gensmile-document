from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import SimulationStatus

SUPPORTED_TREATMENT_TYPES = {
    "ceramic-veneers": "Ceramic Veneers Simulation",
    "orthodontic-alignment": "Orthodontic Alignment Simulation",
    "gum-contouring": "Gum Contouring Simulation",
    "professional-whitening": "Professional Whitening Simulation",
    "composite-bonding": "Composite Bonding Simulation",
    "full-smile-makeover": "Full Smile Makeover Simulation",
}
SUPPORTED_SHADE_PREFERENCES = {
    "a1-brightest",
    "a2-natural",
    "b1-warm",
    "b2-ivory",
    "c1-light",
    "keep-natural",
}
SUPPORTED_SMILE_STYLES = {
    "natural-subtle",
    "noticeably-brighter",
    "dramatic-transformation",
    "hollywood-smile",
}


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized_value = value.strip()
    return normalized_value or None


class SimulationCreateRequest(BaseModel):
    input_image_data_url: str = Field(min_length=32)
    image_name: str | None = Field(default=None, max_length=255)
    patient_id: str | None = Field(default=None, description="Doctor only: patient UUID to create simulation for")

    @field_validator("input_image_data_url")
    @classmethod
    def validate_input_image_data_url(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value.startswith("data:image/"):
            raise ValueError("Input image must be a valid image data URL.")
        return normalized_value

    @field_validator("image_name")
    @classmethod
    def validate_image_name(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)


class SimulationTreatmentUpdateRequest(BaseModel):
    treatment_type: str = Field(min_length=2, max_length=100)

    @field_validator("treatment_type")
    @classmethod
    def validate_treatment_type(cls, value: str) -> str:
        normalized_value = value.strip()
        if normalized_value not in SUPPORTED_TREATMENT_TYPES:
            raise ValueError("Unsupported treatment type.")
        return normalized_value


class SimulationPreferencesUpdateRequest(BaseModel):
    simulation_name: str | None = Field(default=None, max_length=255)
    shade_preference: str | None = Field(default=None, max_length=100)
    smile_style: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("simulation_name", "notes")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)

    @field_validator("shade_preference")
    @classmethod
    def validate_shade_preference(cls, value: str | None) -> str | None:
        normalized_value = _normalize_optional_text(value)
        if normalized_value is None:
            return None
        if normalized_value not in SUPPORTED_SHADE_PREFERENCES:
            raise ValueError("Unsupported shade preference.")
        return normalized_value

    @field_validator("smile_style")
    @classmethod
    def validate_smile_style(cls, value: str | None) -> str | None:
        normalized_value = _normalize_optional_text(value)
        if normalized_value is None:
            return None
        if normalized_value not in SUPPORTED_SMILE_STYLES:
            raise ValueError("Unsupported smile style.")
        return normalized_value


class SimulationGenerateRequest(BaseModel):
    input_image_data_url: str = Field(min_length=32, description="Base64 encoded image data URL")
    simulation_type: str = Field(default="combined", description="ortho | smile | combined")
    shade_style: str | None = Field(default="Natural", description="Natural | Hollywood | Bleach BL1 | Extra OM1 | Warm Natural | Existing")
    resolution: str = Field(default="native", description="native | 1K | 2K | 4K")
    generation_choice: str = Field(default="all", description="only_gif | all")
    additional_notes: str | None = Field(default=None, max_length=2000)
    patient_id: str | None = Field(default=None, description="Doctor only: patient UUID to create simulation for")

    @field_validator("input_image_data_url")
    @classmethod
    def validate_input_image_data_url(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value.startswith("data:image/"):
            raise ValueError("Input image must be a valid image data URL.")
        return normalized_value


class SimulationAnalysisRead(BaseModel):
    alignment_correction: str
    whitening_level: str
    smile_balance: str


class SmileSimulationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    treatment_type: str
    status: SimulationStatus
    input_image_url: str
    output_image_url: str | None = None
    front_view_url: str | None = None
    left_view_url: str | None = None
    right_view_url: str | None = None
    retractor_view_url: str | None = None
    gif_url: str | None = None
    video_url: str | None = None
    shade_preference: str | None = None
    smile_style: str | None = None
    notes: str | None = None
    image_quality_score: int
    ai_confidence_score: int
    generated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    analysis: SimulationAnalysisRead
    is_shareable: bool = Field(default=False, description="Whether the simulation has a valid share link")
    share_expires_at: datetime | None = Field(default=None, description="When the share link expires")
    lab_link_label: str | None = Field(default=None, description="Optional label for lab/link reference")
    patient_name: str | None = Field(default=None, description="Patient full name if linked; None = doctor-only simulation")
    source: str = Field(default="S", description="'W' for Widget/Embed link, 'S' for Self/Studio/Own panel")
    display_status: str = Field(
        default="pending",
        description=(
            "Single source of truth for status labels across the UI: "
            "'image_pending' | 'video_pending' | 'image_generated' | "
            "'pending' (combined image+video request, either phase) | "
            "'completed' | 'failed' | 'in_review'"
        ),
    )
    video_generating: bool = Field(
        default=False,
        description="True while any actor (doctor, patient share link, embed widget) has an in-flight video generation claimed for this simulation -- use to disable the Generate Video button and show a processing state everywhere, not just for whoever started it.",
    )


class SimulationShareResponse(BaseModel):
    share_url: str
    share_token: str
    expires_at: datetime
    valid_for_hours: int = Field(default=72, description="Link validity period in hours")


class SimulationLabLinkUpdateRequest(BaseModel):
    lab_link_label: str | None = Field(default=None, max_length=255, description="Optional label for lab reference")