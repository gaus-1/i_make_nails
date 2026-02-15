from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Текущее время в UTC с tzinfo."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Базовый класс для моделей SQLAlchemy."""


class TimestampMixin:
    """Поля created_at, updated_at для моделей."""

    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
