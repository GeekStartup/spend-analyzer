from fastapi import APIRouter

from app.schemas.health_schema import HealthResponse
from app.services.health_service import get_health_status


router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    return get_health_status()
