"""Дефолт длительности слота 90 мин; существующие мастера с 120 обновить на 90."""

from sqlalchemy import text

from alembic import op

revision = "0004_slot_duration_default_90"
down_revision = "0003_slot_duration_master"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text("UPDATE master SET slot_duration_minutes = 90 WHERE slot_duration_minutes = 120")
    )
    if conn.dialect.name == "postgresql":
        conn.execute(text("ALTER TABLE master ALTER COLUMN slot_duration_minutes SET DEFAULT 90"))


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(text("ALTER TABLE master ALTER COLUMN slot_duration_minutes SET DEFAULT 120"))
