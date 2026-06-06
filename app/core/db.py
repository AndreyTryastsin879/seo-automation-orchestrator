"""Database ORM primitives shared across the project."""

from __future__ import annotations

from datetime import datetime
from typing import Iterator

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy import create_engine

from app.core.config import get_settings


NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

orm_metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """Base declarative class for all ORM models."""

    metadata = orm_metadata


class TimestampMixin:
    """Shared timestamp fields for mutable database rows."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


def create_db_engine() -> Engine:
    """Create the SQLAlchemy engine for the configured database."""

    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )


engine = create_db_engine()

SessionFactory = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_session() -> Iterator[Session]:
    """Yield a database session and close it afterwards."""

    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()
