from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin


class BlockedSlot(TimestampMixin, Base):
    __tablename__ = "blocked_slot"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    master_id: Mapped[int] = mapped_column(ForeignKey("master.id", ondelete="CASCADE"))

    date_start: Mapped[date] = mapped_column(Date)
    date_end: Mapped[date] = mapped_column(Date)

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    master: Mapped["Master"] = relationship(back_populates="blocked_slots")


from bot.models.master import Master  # noqa: E402  # isort: skip

