from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from bot.models import Appointment, BlockedSlot, Master, WorkSchedule


@dataclass
class DailySlots:
    """Container for the list of free slots for a given day."""

    date: date
    slots_utc: list[datetime]


class ScheduleService:
    """Service that knows how to build free slots for a day."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _is_date_blocked(self, master_id: int, target_date: date) -> bool:
        stmt = select(BlockedSlot).where(
            BlockedSlot.master_id == master_id,
            BlockedSlot.date_start <= target_date,
            BlockedSlot.date_end >= target_date,
        )
        return self.db.execute(stmt).first() is not None

    def _get_work_intervals(
        self,
        master_id: int,
        target_date: date,
    ) -> list[tuple[datetime, datetime]]:
        """Return working intervals in master's local time for the given date."""
        master = self.db.get(Master, master_id)
        if master is None:
            msg = f"Master {master_id} not found"
            raise ValueError(msg)

        tz = ZoneInfo(master.timezone)
        weekday = target_date.weekday()

        stmt = select(WorkSchedule).where(
            WorkSchedule.master_id == master_id,
            WorkSchedule.day_of_week == weekday,
        )
        rows = self.db.execute(stmt).scalars().all()
        intervals: list[tuple[datetime, datetime]] = []
        for row in rows:
            start_local = datetime.combine(target_date, row.time_start, tzinfo=tz)
            end_local = datetime.combine(target_date, row.time_end, tzinfo=tz)
            if end_local > start_local:
                intervals.append((start_local, end_local))
        return intervals

    def _get_confirmed_appointments(
        self,
        master_id: int,
        day_start_utc: datetime,
        day_end_utc: datetime,
    ) -> list[tuple[datetime, datetime]]:
        stmt = select(Appointment).where(
            Appointment.master_id == master_id,
            Appointment.status == "confirmed",
            and_(
                Appointment.datetime_start >= day_start_utc,
                Appointment.datetime_start < day_end_utc,
            ),
        )
        appointments = self.db.execute(stmt).scalars().all()

        intervals: list[tuple[datetime, datetime]] = []
        for appointment in appointments:
            start = appointment.datetime_start
            end = appointment.datetime_end
            if start.tzinfo is None:
                start = start.replace(tzinfo=UTC)
            if end.tzinfo is None:
                end = end.replace(tzinfo=UTC)
            intervals.append((start, end))
        return intervals

    @staticmethod
    def _overlaps(
        start: datetime, end: datetime, intervals: list[tuple[datetime, datetime]]
    ) -> bool:
        return any(start < e and end > s for s, e in intervals)

    def get_free_slots_for_date(
        self,
        *,
        master_id: int,
        target_date: date,
        duration_minutes: int,
    ) -> DailySlots:
        """Return list of free slot start times in UTC for a given date."""
        master = self.db.get(Master, master_id)
        if master is None:
            msg = f"Master {master_id} not found"
            raise ValueError(msg)

        if not master.booking_enabled:
            return DailySlots(date=target_date, slots_utc=[])

        if self._is_date_blocked(master_id, target_date):
            return DailySlots(date=target_date, slots_utc=[])

        tz = ZoneInfo(master.timezone)
        intervals_local = self._get_work_intervals(master_id, target_date)
        if not intervals_local:
            return DailySlots(date=target_date, slots_utc=[])

        day_start_local = datetime.combine(target_date, time(0, 0), tzinfo=tz)
        day_end_local = day_start_local + timedelta(days=1)
        day_start_utc = day_start_local.astimezone(UTC)
        day_end_utc = day_end_local.astimezone(UTC)

        busy_intervals_utc = self._get_confirmed_appointments(
            master_id=master_id,
            day_start_utc=day_start_utc,
            day_end_utc=day_end_utc,
        )

        result_slots: list[datetime] = []

        step = timedelta(minutes=duration_minutes)
        for start_local, end_local in intervals_local:
            current = start_local
            while current + step <= end_local:
                slot_start_utc = current.astimezone(UTC)
                slot_end_utc = slot_start_utc + step
                if not self._overlaps(slot_start_utc, slot_end_utc, busy_intervals_utc):
                    result_slots.append(slot_start_utc)
                current += step

        return DailySlots(date=target_date, slots_utc=result_slots)
