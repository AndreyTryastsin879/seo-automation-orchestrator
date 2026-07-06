"""Central registry of ORM models for metadata discovery."""

from app.modules.bot_access.infrastructure import BotAccessUser
from app.modules.projects.infrastructure import Project
from app.modules.tasks.infrastructure import Task, TaskFile

__all__ = ["BotAccessUser", "Project", "Task", "TaskFile"]
