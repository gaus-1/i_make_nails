from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin


class Appointment(TimestampMixin, Base):
    """Запись клиента на слот: мастер, клиент, услуга, время, статус."""

    __tablename__ = "appointment"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    master_id: Mapped[int] = mapped_column(ForeignKey("master.id", ondelete="CASCADE"))
    client_id: Mapped[int] = mapped_column(ForeignKey("client.id", ondelete="CASCADE"))
    service_id: Mapped[int] = mapped_column(ForeignKey("service.id", ondelete="RESTRICT"))

    datetime_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    datetime_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    status: Mapped[str] = mapped_column(String(32), default="confirmed", index=True)
    source: Mapped[str] = mapped_column(String(32), default="client")

    reminder_24h_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reminder_2h_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    client: Mapped["Client"] = relationship(back_populates="appointments")
    service: Mapped["Service"] = relationship(back_populates="appointments")
    master: Mapped["Master"] = relationship(back_populates="appointments")


from bot.models.client import Client  # noqa: E402  # isort: skip
from bot.models.service import Service  # noqa: E402  # isort: skip
from bot.models.master import Master  # noqa: E402  # isort: skip
