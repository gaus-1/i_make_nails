"""Подключение к БД и фабрика сессий."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from bot.config.settings import settings

# Railway DATABASE_URL часто без +psycopg — подставляем драйвер
_db_url = settings.database_url
if _db_url.startswith("postgresql://") and "+psycopg" not in _db_url:
    _db_url = _db_url.replace("postgresql://", "postgresql+psycopg://", 1)

# Пул под одновременные запросы мини-аппа (по умолчанию 5+10 мало при пиках)
engine = create_engine(
    _db_url,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=30,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Контекстный менеджер сессии БД."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
