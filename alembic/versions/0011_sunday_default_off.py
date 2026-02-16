"""Воскресенье (day_of_week=6) по умолчанию выходной: 00:00–00:00, слотов нет."""

from sqlalchemy import text

from alembic import op

revision = "0011_sunday_default_off"
down_revision = "0010_work_schedule_start_08_00"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "UPDATE work_schedule SET time_start = '00:00:00', time_end = '00:00:00' WHERE day_of_week = 6"
        )
    )


def downgrade() -> None:
    pass
