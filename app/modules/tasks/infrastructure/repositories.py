"""Repositories for the tasks module."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.tasks.domain import TaskBatchStatus, TaskStatus
from app.modules.tasks.infrastructure.models import Task, TaskBatch, TaskFile


class TaskBatchRepository:
    """Data access layer for task batch records."""

    def __init__(self, session: Session) -> None:
        """Bind repository to an existing SQLAlchemy session."""

        self._session = session

    def create(self, task_batch: TaskBatch) -> TaskBatch:
        """Persist a new task batch instance."""

        self._session.add(task_batch)
        self._session.flush()
        return task_batch

    def get_by_id(self, batch_id: int) -> TaskBatch | None:
        """Return a task batch by its primary key."""

        statement = select(TaskBatch).where(TaskBatch.id == batch_id)
        return self._session.scalar(statement)

    def list(self) -> list[TaskBatch]:
        """Return all task batches ordered by identifier."""

        statement = select(TaskBatch).order_by(TaskBatch.id)
        return list(self._session.scalars(statement).all())

    def list_recent(self, *, limit: int) -> list[TaskBatch]:
        """Return recent task batches ordered from newest to oldest."""

        statement = select(TaskBatch).order_by(TaskBatch.id.desc()).limit(limit)
        return list(self._session.scalars(statement).all())

    def list_by_statuses(self, *, statuses: tuple[TaskBatchStatus, ...]) -> list[TaskBatch]:
        """Return task batches filtered by status values."""

        statement = (
            select(TaskBatch)
            .where(TaskBatch.status.in_(statuses))
            .order_by(TaskBatch.id)
        )
        return list(self._session.scalars(statement).all())

    def update(self, task_batch: TaskBatch) -> TaskBatch:
        """Flush changes for an existing task batch instance."""

        self._session.add(task_batch)
        self._session.flush()
        return task_batch


class TaskRepository:
    """Data access layer for task records."""

    def __init__(self, session: Session) -> None:
        """Bind repository to an existing SQLAlchemy session."""

        self._session = session

    def create(self, task: Task) -> Task:
        """Persist a new task instance."""

        self._session.add(task)
        self._session.flush()
        return task

    def get_by_id(self, task_id: int) -> Task | None:
        """Return a task by its primary key."""

        statement = select(Task).where(Task.id == task_id)
        return self._session.scalar(statement)

    def list(self) -> list[Task]:
        """Return all tasks ordered by identifier."""

        statement = select(Task).order_by(Task.id)
        return list(self._session.scalars(statement).all())

    def list_by_batch_id(self, batch_id: int) -> list[Task]:
        """Return all tasks that belong to a task batch."""

        statement = select(Task).where(Task.batch_id == batch_id).order_by(Task.id)
        return list(self._session.scalars(statement).all())

    def list_by_statuses(self, *, statuses: tuple[TaskStatus, ...]) -> list[Task]:
        """Return tasks filtered by status values."""

        statement = (
            select(Task)
            .where(Task.status.in_(statuses))
            .order_by(Task.id)
        )
        return list(self._session.scalars(statement).all())

    def list_by_task_type_and_statuses(
        self,
        *,
        task_type: str,
        statuses: tuple[TaskStatus, ...],
    ) -> list[Task]:
        """Return tasks filtered by task type and statuses."""

        statement = (
            select(Task)
            .where(Task.task_type == task_type)
            .where(Task.status.in_(statuses))
            .order_by(Task.id)
        )
        return list(self._session.scalars(statement).all())

    def update(self, task: Task) -> Task:
        """Flush changes for an existing task instance."""

        self._session.add(task)
        self._session.flush()
        return task

    def delete(self, task: Task) -> None:
        """Delete an existing task instance."""

        self._session.delete(task)
        self._session.flush()


class TaskFileRepository:
    """Data access layer for task file records."""

    def __init__(self, session: Session) -> None:
        """Bind repository to an existing SQLAlchemy session."""

        self._session = session

    def create(self, task_file: TaskFile) -> TaskFile:
        """Persist a new task file instance."""

        self._session.add(task_file)
        self._session.flush()
        return task_file

    def list_by_task_id(self, task_id: int) -> list[TaskFile]:
        """Return all files created for a specific task."""

        statement = select(TaskFile).where(TaskFile.task_id == task_id).order_by(TaskFile.id)
        return list(self._session.scalars(statement).all())
