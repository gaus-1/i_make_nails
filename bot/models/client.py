from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin


class Client(TimestampMixin, Base):
    """Клиент мастера: telegram_id, контакт, право на запись."""

    __tablename__ = "client"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    master_id: Mapped[int] = mapped_column(ForeignKey("master.id", ondelete="CASCADE"))

    telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    booking_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(32), default="bot")

    master: Mapped["Master"] = relationship(back_populates="clients")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="client")


from bot.models.master import Master  # noqa: E402  # isort: skip
from bot.models.appointment import Appointment  # noqa: E402  # isort: skip
