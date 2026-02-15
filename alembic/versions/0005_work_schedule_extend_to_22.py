"""Расширить рабочие часы до 22:00, если сейчас раньше."""

from sqlalchemy import text

from alembic import op

revision = "0005_work_schedule_extend_to_22"
down_revision = "0004_slot_duration_default_90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    # Расширяем до 22:00 только те дни, где время окончания раньше 22:00
    conn.execute(
        text("UPDATE work_schedule SET time_end = '22:00:00' " "WHERE time_end < '22:00:00'")
    )


def downgrade() -> None:
    # Не восстанавливаем старые значения — неизвестны
    pass
