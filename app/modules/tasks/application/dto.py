"""Application DTOs for the tasks module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.modules.tasks.domain import JsonPayload, TaskBatchStatus, TaskBatchType, TaskStatus


@dataclass(slots=True, frozen=True)
class CreateTaskBatchCommand:
    """Input data for creating a task batch."""

    batch_type: TaskBatchType
    title: str
    payload: JsonPayload | None = None
    status: TaskBatchStatus = TaskBatchStatus.PENDING


@dataclass(slots=True, frozen=True)
class CreateTaskCommand:
    """Input data for creating a task."""

    batch_id: int | None
    project_id: int | None
    queue_name: str | None
    task_type: str
    payload: JsonPayload | None = None
    status: TaskStatus = TaskStatus.PENDING


@dataclass(slots=True, frozen=True)
class TaskBatchDTO:
    """Application representation of a task batch."""

    id: int
    batch_type: TaskBatchType
    title: str
    status: TaskBatchStatus
    payload: JsonPayload | None
    result_payload: JsonPayload | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(slots=True, frozen=True)
class TaskDTO:
    """Application representation of a task."""

    id: int
    batch_id: int | None
    project_id: int | None
    queue_name: str | None
    task_type: str
    status: TaskStatus
    payload: JsonPayload | None
    result_payload: JsonPayload | None
    cancel_requested: bool
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(slots=True, frozen=True)
class TaskFileDTO:
    """Application representation of a task file."""

    id: int
    task_id: int
    file_name: str
    file_path: str
    file_type: str | None
    file_size: int | None
    created_at: datetime
