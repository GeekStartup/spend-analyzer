from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health_routes import router as health_router
from app.api.ingest_routes import router as ingest_router
from app.api.me_routes import router as me_router
from app.config import settings
from app.observability.logging import configure_logging, get_logger
from app.observability.metrics import configure_http_metrics
from app.observability.middleware import RequestContextMiddleware
from app.observability.tracing import configure_tracing
from app.problem_details import register_problem_handlers

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info(
        "Application started",
        environment=settings.app_env,
        version=settings.app_version,
    )
    try:
        yield
    finally:
        logger.info(
            "Application stopped",
            environment=settings.app_env,
            version=settings.app_version,
        )


def create_app() -> FastAPI:
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        description="Spend Analyzer API",
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(RequestContextMiddleware, metrics_path=settings.metrics_path)
    register_problem_handlers(app)

    configure_tracing(
        app,
        enabled=settings.tracing_enabled,
        service_name=settings.otel_service_name,
        otlp_endpoint=settings.otel_exporter_otlp_endpoint,
        sample_ratio=settings.otel_sample_ratio,
        excluded_urls=settings.metrics_path,
        excluded_outbound_urls=(
            settings.oidc_jwks_url,
            settings.oidc_issuer_url,
        ),
    )

    app.include_router(health_router)
    app.include_router(me_router)
    app.include_router(ingest_router)

    configure_http_metrics(
        app,
        enabled=settings.metrics_enabled,
        metrics_path=settings.metrics_path,
    )

    return app


app = create_app()
