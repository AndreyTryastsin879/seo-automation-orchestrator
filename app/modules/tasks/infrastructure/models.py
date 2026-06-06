"""SQLAlchemy models for the tasks module."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin
from app.modules.tasks.domain import JsonPayload, TaskBatchStatus, TaskBatchType, TaskStatus

if TYPE_CHECKING:
    from app.modules.projects.infrastructure.models import Project


class TaskBatch(TimestampMixin, Base):
    """Task batch ORM model."""

    __tablename__ = "task_batches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_type: Mapped[TaskBatchType] = mapped_column(
        Enum(
            TaskBatchType,
            name="task_batch_type",
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[TaskBatchStatus] = mapped_column(
        Enum(
            TaskBatchStatus,
            name="task_batch_status",
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
        default=TaskBatchStatus.PENDING,
        server_default=TaskBatchStatus.PENDING.value,
        index=True,
    )
    payload: Mapped[JsonPayload | None] = mapped_column(JSONB, nullable=True)
    result_payload: Mapped[JsonPayload | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class Task(TimestampMixin, Base):
    """Task ORM model."""

    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_batch_id_status", "batch_id", "status"),
        Index("ix_tasks_project_id_status", "project_id", "status"),
        Index("ix_tasks_project_id_task_type", "project_id", "task_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("task_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    queue_name: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(
            TaskStatus,
            name="task_status",
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
        default=TaskStatus.PENDING,
        server_default=TaskStatus.PENDING.value,
        index=True,
    )
    payload: Mapped[JsonPayload | None] = mapped_column(JSONB, nullable=True)
    result_payload: Mapped[JsonPayload | None] = mapped_column(JSONB, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    batch: Mapped["TaskBatch | None"] = relationship(back_populates="tasks")
    project: Mapped["Project | None"] = relationship(back_populates="tasks")
    files: Mapped[list["TaskFile"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )


class TaskFile(Base):
    """Task output file ORM model."""

    __tablename__ = "task_files"
    __table_args__ = (
        Index("ix_task_files_task_id_file_name", "task_id", "file_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    task: Mapped["Task"] = relationship(back_populates="files")
