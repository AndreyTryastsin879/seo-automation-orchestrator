"""API routers package."""

from app.interfaces.api.routers.projects import router as projects_router
from app.interfaces.api.routers.tasks import router as tasks_router

__all__ = ["projects_router", "tasks_router"]
