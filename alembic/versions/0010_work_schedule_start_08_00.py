"""Начало смены 8:00 — первая запись 8:00–9:30."""

from sqlalchemy import text

from alembic import op

revision = "0010_work_schedule_start_08_00"
down_revision = "0009_work_schedule_end_21_30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("UPDATE work_schedule SET time_start = '08:00:00'"))


def downgrade() -> None:
    pass
