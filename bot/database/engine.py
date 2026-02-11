"""Подключение к БД и фабрика сессий. Сессии для HTTP берут через bot.api.deps.get_db()."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bot.config.settings import settings

# Railway DATABASE_URL часто без +psycopg — подставляем драйвер
_db_url = settings.database_url
if _db_url.startswith("postgresql://") and "+psycopg" not in _db_url:
    _db_url = _db_url.replace("postgresql://", "postgresql+psycopg://", 1)

_engine_kwargs: dict = {}
if "sqlite" not in _db_url:
    _engine_kwargs = {"pool_pre_ping": True, "pool_size": 20, "max_overflow": 30}
engine = create_engine(_db_url, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
