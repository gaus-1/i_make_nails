"""Окончание смены 21:30 — слоты 8:00–9:30 … 20:00–21:30."""

from sqlalchemy import text

from alembic import op

revision = "0009_work_schedule_end_21_30"
down_revision = "0008_work_schedule_end_2230"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("UPDATE work_schedule SET time_end = '21:30:00'"))


def downgrade() -> None:
    pass
