"""Длительность слота у мастера; запись без привязки к услуге."""

import sqlalchemy as sa

from alembic import op

revision = "0002_slot_duration_no_services"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "master",
        sa.Column("slot_duration_minutes", sa.Integer(), nullable=False, server_default="120"),
    )
    with op.batch_alter_table("appointment") as batch_op:
        batch_op.alter_column(
            "service_id",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("appointment") as batch_op:
        batch_op.alter_column(
            "service_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
    op.drop_column("master", "slot_duration_minutes")
