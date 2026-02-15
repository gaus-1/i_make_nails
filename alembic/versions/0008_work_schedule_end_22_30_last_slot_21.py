"""Окончание смены 22:30 — последний слот 21:00 (21:00–22:30)."""

from sqlalchemy import text

from alembic import op

revision = "0008_work_schedule_end_22_30_last_slot_21"
down_revision = "0007_work_schedule_end_21_00"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("UPDATE work_schedule SET time_end = '22:30:00'"))


def downgrade() -> None:
    pass
