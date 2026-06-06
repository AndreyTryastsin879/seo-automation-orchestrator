"""SQLAlchemy models for the projects module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin
from app.modules.projects.domain import CrawlSegment

if TYPE_CHECKING:
    from app.modules.tasks.infrastructure.models import Task


class Project(TimestampMixin, Base):
    """Project ORM model."""

    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_start_url", "start_url"),
        Index("ix_projects_yandex_webmaster_host", "yandex_webmaster_host"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    sitemap_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    crawl_segment: Mapped[CrawlSegment] = mapped_column(
        Enum(
            CrawlSegment,
            name="crawl_segment",
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
        default=CrawlSegment.DEFAULT,
        server_default=CrawlSegment.DEFAULT.value,
        index=True,
    )
    is_multi_sitemap: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    pagination_view: Mapped[str | None] = mapped_column(String(50), nullable=True)
    yandex_webmaster_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pagination_sample: Mapped[str | None] = mapped_column(Text, nullable=True)
    pagination_marker: Mapped[str | None] = mapped_column(String(255), nullable=True)
    card_sample: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_sample: Mapped[str | None] = mapped_column(Text, nullable=True)
    contain_subdomains: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
