"""Окончание рабочего дня 22:30."""

from sqlalchemy import text

from alembic import op

revision = "0006_work_schedule_end_22_30"
down_revision = "0005_work_schedule_extend_to_22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("UPDATE work_schedule SET time_end = '22:30:00'"))


def downgrade() -> None:
    pass
