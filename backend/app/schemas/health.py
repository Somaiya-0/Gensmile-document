from pydantic import BaseModel


class HealthCheckResponse(BaseModel):
    service: str
    environment: str
    version: str
    status: str
