"""Initial schema for i-make-nails bot."""

from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def upgrade() -> None:
    op.create_table(
        "master",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger(), unique=True, nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Europe/Moscow"),
        sa.Column("booking_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, default=_utc_now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, default=_utc_now),
    )

    op.create_table(
        "client",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("master_id", sa.Integer(), sa.ForeignKey("master.id", ondelete="CASCADE")),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("booking_allowed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="bot"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, default=_utc_now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, default=_utc_now),
    )
    op.create_index(
        "ix_client_telegram_id",
        "client",
        ["telegram_id"],
    )

    op.create_table(
        "service",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("master_id", sa.Integer(), sa.ForeignKey("master.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("price_rub", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, default=_utc_now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, default=_utc_now),
    )

    op.create_table(
        "blocked_slot",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("master_id", sa.Integer(), sa.ForeignKey("master.id", ondelete="CASCADE")),
        sa.Column("date_start", sa.Date(), nullable=False),
        sa.Column("date_end", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, default=_utc_now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, default=_utc_now),
    )

    op.create_table(
        "work_schedule",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("master_id", sa.Integer(), sa.ForeignKey("master.id", ondelete="CASCADE")),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("time_start", sa.Time(), nullable=False),
        sa.Column("time_end", sa.Time(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, default=_utc_now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, default=_utc_now),
    )

    op.create_table(
        "appointment",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("master_id", sa.Integer(), sa.ForeignKey("master.id", ondelete="CASCADE")),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("client.id", ondelete="CASCADE")),
        sa.Column(
            "service_id",
            sa.Integer(),
            sa.ForeignKey("service.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("datetime_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("datetime_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="confirmed"),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="client"),
        sa.Column("reminder_24h_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminder_2h_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, default=_utc_now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, default=_utc_now),
    )
    op.create_index(
        "ix_appointment_datetime_start",
        "appointment",
        ["datetime_start"],
    )
    op.create_index(
        "ix_appointment_status",
        "appointment",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_appointment_status", table_name="appointment")
    op.drop_index("ix_appointment_datetime_start", table_name="appointment")
    op.drop_table("appointment")

    op.drop_table("work_schedule")
    op.drop_table("blocked_slot")
    op.drop_table("service")

    op.drop_index("ix_client_telegram_id", table_name="client")
    op.drop_table("client")

    op.drop_table("master")
