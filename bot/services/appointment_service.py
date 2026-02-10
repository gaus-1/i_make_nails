from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.models import Appointment, Client, Master, Service
from bot.services.exceptions import AppointmentNotFoundError, SlotBusyError


class AppointmentService:
    """Service responsible for creating and updating appointments."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _check_slot_free(
        self,
        master_id: int,
        start_utc: datetime,
        end_utc: datetime,
        ignore_appointment_id: int | None = None,
    ) -> None:
        """Ensure there is no overlapping confirmed appointment for the master."""
        if start_utc.tzinfo is None or end_utc.tzinfo is None:
            msg = "start_utc and end_utc must be timezone-aware in UTC"
            raise ValueError(msg)

        stmt = select(Appointment).where(
            Appointment.master_id == master_id,
            Appointment.status == "confirmed",
            Appointment.datetime_start < end_utc,
            Appointment.datetime_end > start_utc,
        )

        if ignore_appointment_id is not None:
            stmt = stmt.where(Appointment.id != ignore_appointment_id)

        # FOR UPDATE is ignored by SQLite but works on PostgreSQL, which we use in prod.
        appointments = self.db.execute(stmt.with_for_update()).scalars().all()
        if appointments:
            raise SlotBusyError("Requested time slot is already occupied.")

    def create(
        self,
        *,
        master_id: int,
        client_id: int,
        service_id: int,
        datetime_start_utc: datetime,
    ) -> Appointment:
        """Create a new appointment after checking that the time slot is free."""
        service = self.db.get(Service, service_id)
        master = self.db.get(Master, master_id)
        client = self.db.get(Client, client_id)

        if service is None or master is None or client is None:
            msg = "Invalid master, client or service id"
            raise ValueError(msg)

        if datetime_start_utc.tzinfo is None:
            datetime_start_utc = datetime_start_utc.replace(tzinfo=timezone.utc)

        datetime_end_utc = datetime_start_utc + timedelta(minutes=service.duration_minutes)

        self._check_slot_free(master_id=master.id, start_utc=datetime_start_utc, end_utc=datetime_end_utc)

        appointment = Appointment(
            master_id=master.id,
            client_id=client.id,
            service_id=service.id,
            datetime_start=datetime_start_utc,
            datetime_end=datetime_end_utc,
            status="confirmed",
            source="client",
        )
        self.db.add(appointment)
        self.db.commit()
        self.db.refresh(appointment)
        return appointment

    def reschedule(
        self,
        *,
        appointment_id: int,
        new_datetime_start_utc: datetime,
    ) -> Appointment:
        """Move an existing appointment to a new free time slot."""
        appointment = self.db.get(Appointment, appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError(f"Appointment {appointment_id} not found.")

        if new_datetime_start_utc.tzinfo is None:
            new_datetime_start_utc = new_datetime_start_utc.replace(tzinfo=timezone.utc)

        new_end_utc = new_datetime_start_utc + (
            appointment.datetime_end - appointment.datetime_start
        )

        self._check_slot_free(
            master_id=appointment.master_id,
            start_utc=new_datetime_start_utc,
            end_utc=new_end_utc,
            ignore_appointment_id=appointment.id,
        )

        appointment.datetime_start = new_datetime_start_utc
        appointment.datetime_end = new_end_utc
        # сбрасывать флаги напоминаний будем позже, когда добавим их в логику

        self.db.add(appointment)
        self.db.commit()
        self.db.refresh(appointment)
        return appointment

