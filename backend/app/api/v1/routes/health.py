from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.health import HealthCheckResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "",
    response_model=HealthCheckResponse,
    summary="Health check",
    description=(
        "Returns the service name, current version, deployment environment, and status. "
        "Use this endpoint for uptime monitoring and deployment verification. "
        "No authentication required."
    ),
)
async def health_check() -> HealthCheckResponse:
    settings = get_settings()
    return HealthCheckResponse(
        service=settings.project_name,
        environment=settings.environment,
        version=settings.version,
        status="ok",
    )
