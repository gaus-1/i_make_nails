"""Окончание рабочего дня 21:00."""

from sqlalchemy import text

from alembic import op

revision = "0007_work_schedule_end_21_00"
down_revision = "0006_work_schedule_end_22_30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("UPDATE work_schedule SET time_end = '21:00:00'"))


def downgrade() -> None:
    pass
