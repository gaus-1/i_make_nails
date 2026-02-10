from sqlalchemy import create_engine

from bot.models import Base


def test_metadata_creates_successfully() -> None:
    """Smoke-test that all models can be created in an in-memory database."""
    engine = create_engine("sqlite+pysqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)

