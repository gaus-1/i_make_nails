from datetime import time

from sqlalchemy import ForeignKey, Integer, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base, TimestampMixin


class WorkSchedule(TimestampMixin, Base):
    """Рабочие часы мастера по дню недели (0=Пн, 6=Вс)."""

    __tablename__ = "work_schedule"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    master_id: Mapped[int] = mapped_column(ForeignKey("master.id", ondelete="CASCADE"))

    day_of_week: Mapped[int] = mapped_column(Integer)  # 0=Monday ... 6=Sunday
    time_start: Mapped[time] = mapped_column(Time)
    time_end: Mapped[time] = mapped_column(Time)

    master: Mapped["Master"] = relationship(back_populates="work_schedule")


from bot.models.master import Master  # noqa: E402  # isort: skip
