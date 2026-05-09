from fastapi import APIRouter, HTTPException, status
from psycopg import Error as PsycopgError

from app.db.connection import check_database_connection
from app.schemas.health_schema import HealthResponse
from app.services.health_service import get_health_status


router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    return get_health_status()


@router.get("/health/db")
def database_helath_check():
    try:
        is_connected = check_database_connection()
    except PsycopgError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "ERROR",
                "service": "database",
                "message": "Database is not reachable",
                "error": error.__class__.__name__,
            },
        ) from error

    if not is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "ERROR",
                "service": "database",
                "message": "Database health check failed",
            },
        )

    return {
        "status": "OK",
        "service": "database",
        "message": "Database is reachable",
    }
