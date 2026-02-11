"""Добавить slot_duration_minutes в master, если колонки ещё нет (PostgreSQL)."""

import sqlalchemy as sa
from sqlalchemy import inspect, text

from alembic import op

revision = "0003_master_slot_duration_if_not_exists"
down_revision = "0002_slot_duration_no_services"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    dialect_name = conn.dialect.name
    insp = inspect(conn)
    cols = [c["name"] for c in insp.get_columns("master")]
    if "slot_duration_minutes" in cols:
        return
    if dialect_name == "postgresql":
        conn.execute(
            text("ALTER TABLE master ADD COLUMN slot_duration_minutes INTEGER NOT NULL DEFAULT 120")
        )
    else:
        op.add_column(
            "master",
            sa.Column("slot_duration_minutes", sa.Integer(), nullable=False, server_default="120"),
        )


def downgrade() -> None:
    # Колонку могла добавить 0002 — не трогаем.
    pass
