from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin


class Master(TimestampMixin, Base):
    __tablename__ = "master"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    booking_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    services: Mapped[list["Service"]] = relationship(back_populates="master")
    clients: Mapped[list["Client"]] = relationship(back_populates="master")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="master")
    blocked_slots: Mapped[list["BlockedSlot"]] = relationship(back_populates="master")
    work_schedule: Mapped[list["WorkSchedule"]] = relationship(back_populates="master")


from bot.models.client import Client  # noqa: E402  # isort: skip
from bot.models.service import Service  # noqa: E402  # isort: skip
from bot.models.appointment import Appointment  # noqa: E402  # isort: skip
from bot.models.blocked_slot import BlockedSlot  # noqa: E402  # isort: skip
from bot.models.work_schedule import WorkSchedule  # noqa: E402  # isort: skip
