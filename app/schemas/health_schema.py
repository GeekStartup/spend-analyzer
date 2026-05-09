from typing import Literal

from pydantic import BaseModel


HealthStatus = Literal["OK", "ERROR"]


class ServiceMetadata(BaseModel):
    name: str
    environment: str
    version: str


class HealthCheck(BaseModel):
    status: HealthStatus
    message: str
    error: str | None = None


class HealthResponse(BaseModel):
    status: HealthStatus
    service: ServiceMetadata
    checks: dict[str, HealthCheck]
