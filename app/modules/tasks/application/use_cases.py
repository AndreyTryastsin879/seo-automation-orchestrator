"""Use cases for the tasks module."""

from __future__ import annotations

from app.modules.tasks.application.dto import (
    CreateTaskBatchCommand,
    CreateTaskCommand,
    TaskBatchDTO,
    TaskDTO,
    TaskFileDTO,
)
from app.modules.tasks.infrastructure.models import Task, TaskBatch, TaskFile
from app.modules.tasks.infrastructure.repositories import TaskBatchRepository, TaskFileRepository, TaskRepository


def _to_task_batch_dto(task_batch: TaskBatch) -> TaskBatchDTO:
    """Convert an ORM task batch model to an application DTO."""

    return TaskBatchDTO(
        id=task_batch.id,
        batch_type=task_batch.batch_type,
        title=task_batch.title,
        status=task_batch.status,
        payload=task_batch.payload,
        result_payload=task_batch.result_payload,
        error_message=task_batch.error_message,
        created_at=task_batch.created_at,
        updated_at=task_batch.updated_at,
        started_at=task_batch.started_at,
        finished_at=task_batch.finished_at,
    )


def _to_task_dto(task: Task) -> TaskDTO:
    """Convert an ORM task model to an application DTO."""

    return TaskDTO(
        id=task.id,
        batch_id=task.batch_id,
        project_id=task.project_id,
        queue_name=task.queue_name,
        task_type=task.task_type,
        status=task.status,
        payload=task.payload,
        result_payload=task.result_payload,
        cancel_requested=task.cancel_requested,
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
    )


def _to_task_file_dto(task_file: TaskFile) -> TaskFileDTO:
    """Convert an ORM task file model to an application DTO."""

    return TaskFileDTO(
        id=task_file.id,
        task_id=task_file.task_id,
        file_name=task_file.file_name,
        file_path=task_file.file_path,
        file_type=task_file.file_type,
        file_size=task_file.file_size,
        created_at=task_file.created_at,
    )


class CreateTaskUseCase:
    """Create a new task record."""

    def __init__(self, repository: TaskRepository) -> None:
        """Bind the use case to a task repository."""

        self._repository = repository

    def execute(self, command: CreateTaskCommand) -> TaskDTO:
        """Create a task and return its application DTO."""

        task = Task(
            batch_id=command.batch_id,
            project_id=command.project_id,
            queue_name=command.queue_name,
            task_type=command.task_type,
            payload=command.payload,
            status=command.status,
        )
        created_task = self._repository.create(task)
        return _to_task_dto(created_task)


class CreateTaskBatchUseCase:
    """Create a new task batch record."""

    def __init__(self, repository: TaskBatchRepository) -> None:
        """Bind the use case to a task batch repository."""

        self._repository = repository

    def execute(self, command: CreateTaskBatchCommand) -> TaskBatchDTO:
        """Create a task batch and return its application DTO."""

        task_batch = TaskBatch(
            batch_type=command.batch_type,
            title=command.title,
            payload=command.payload,
            status=command.status,
        )
        created_batch = self._repository.create(task_batch)
        return _to_task_batch_dto(created_batch)


class GetTaskUseCase:
    """Return a task by identifier."""

    def __init__(self, repository: TaskRepository) -> None:
        """Bind the use case to a task repository."""

        self._repository = repository

    def execute(self, task_id: int) -> TaskDTO | None:
        """Return a task DTO or None when it does not exist."""

        task = self._repository.get_by_id(task_id)
        if task is None:
            return None
        return _to_task_dto(task)


class ListTasksUseCase:
    """Return the list of tasks."""

    def __init__(self, repository: TaskRepository) -> None:
        """Bind the use case to a task repository."""

        self._repository = repository

    def execute(self) -> list[TaskDTO]:
        """Return all tasks as application DTOs."""

        tasks = self._repository.list()
        return [_to_task_dto(task) for task in tasks]


class ListTaskFilesUseCase:
    """Return the list of files created for a task."""

    def __init__(self, repository: TaskFileRepository) -> None:
        """Bind the use case to a task file repository."""

        self._repository = repository

    def execute(self, task_id: int) -> list[TaskFileDTO]:
        """Return all task files as application DTOs."""

        task_files = self._repository.list_by_task_id(task_id)
        return [_to_task_file_dto(task_file) for task_file in task_files]
