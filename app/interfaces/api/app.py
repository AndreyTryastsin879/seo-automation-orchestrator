"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy.orm import configure_mappers

import app.core.models  # noqa: F401
from app.core.logging import configure_logging, get_logger, log_event
from app.interfaces.api.routers import projects_router, tasks_router

LOGGER = get_logger("app.api")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    configure_logging(service="api")
    # Import the central ORM registry before serving requests so SQLAlchemy
    # can resolve string-based relationships across modules.
    configure_mappers()
    app = FastAPI(title="Mega Tools API")

    @app.get("/health")
    def healthcheck() -> dict[str, str]:
        """Return a simple API healthcheck response."""

        return {"status": "ok"}

    app.include_router(projects_router)
    app.include_router(tasks_router)
    log_event(LOGGER, "api_configured")
    return app
