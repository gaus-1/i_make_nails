from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from aiohttp import web
from sqlalchemy import and_, select
from sqlalchemy.orm import joinedload

from bot.api.deps import (
    _get_single_master_id,
    conflict,
    forbidden,
    get_telegram_id,
    not_found,
    parse_date,
    parse_int,
    require_master,
)
from bot.api.schemas import (
    AppointmentCreateIn,
    AppointmentOut,
    AppointmentRescheduleIn,
    AppointmentsListResponse,
    MasterAppointmentOut,
    MasterAppointmentsResponse,
    ServiceOut,
    ServicesResponse,
    SlotOut,
    SlotsResponse,
)
from bot.database import SessionLocal
from bot.models import Appointment, Client, Master, Service
from bot.services import AppointmentService, ScheduleService
from bot.services.exceptions import SlotBusyError


routes = web.RouteTableDef()


@routes.get("/api/miniapp/services")
async def get_services(request: web.Request) -> web.Response:  # noqa: D401
    """Return list of active services for the master."""
    with SessionLocal() as db:
        master_id = _get_single_master_id(db)
        stmt = (
            select(Service)
            .where(Service.master_id == master_id, Service.is_active.is_(True))
            .order_by(Service.sort_order, Service.id)
        )
        services = db.execute(stmt).scalars().all()
        services_out = [ServiceOut.model_validate(svc) for svc in services]

    body = ServicesResponse(services=services_out)
    return web.json_response(body.model_dump(mode="json"))


@routes.get("/api/miniapp/slots")
async def get_free_slots(request: web.Request) -> web.Response:  # noqa: D401
    """Return free slots for a given date and service."""
    target_date = parse_date("date", request.query.get("date"))
    service_id = parse_int("service_id", request.query.get("service_id"))

    with SessionLocal() as db:
        service = db.get(Service, service_id)
        if service is None or not service.is_active:
            not_found("Услуга не найдена.", code="service_not_found")

        master_id = service.master_id
        schedule = ScheduleService(db)
        daily_slots = schedule.get_free_slots_for_date(
            master_id=master_id,
            target_date=target_date,
            duration_minutes=service.duration_minutes,
        )
        slots = [SlotOut(start_utc_iso=slot.isoformat()) for slot in daily_slots.slots_utc]

    body = SlotsResponse(date=daily_slots.date.isoformat(), slots=slots)
    return web.json_response(body.model_dump(mode="json"))


@routes.get("/api/miniapp/appointments/my")
async def get_my_appointments(request: web.Request) -> web.Response:
    """Return list of appointments for current client."""
    telegram_id = get_telegram_id(request)

    with SessionLocal() as db:
        master_id = _get_single_master_id(db)

        client_stmt = select(Client).where(
            Client.master_id == master_id,
            Client.telegram_id == telegram_id,
        )
        client = db.execute(client_stmt).scalars().first()
        if client is None:
            body = AppointmentsListResponse(appointments=[])
            return web.json_response(body.model_dump(mode="json"))

        now_utc = datetime.now(UTC)
        history_limit_days = 30
        cutoff = now_utc - timedelta(days=history_limit_days)

        stmt = (
            select(Appointment)
            .options(joinedload(Appointment.service))
            .where(
                Appointment.client_id == client.id,
                Appointment.status.in_(("confirmed", "completed", "no_show")),
                Appointment.datetime_start >= cutoff,
            )
            .order_by(Appointment.datetime_start)
        )
        appointments = db.execute(stmt).scalars().all()

        items = [
            AppointmentOut(
                id=appt.id,
                service_name=appt.service.name,
                datetime_start_utc=appt.datetime_start,
                status=appt.status,
                source=appt.source,
            )
            for appt in appointments
        ]

    body = AppointmentsListResponse(appointments=items)
    return web.json_response(body.model_dump(mode="json"))


@routes.post("/api/miniapp/appointments")
async def create_appointment(request: web.Request) -> web.Response:
    """Create a new appointment for client in mini-app."""
    payload_raw = await request.json()
    data = AppointmentCreateIn.model_validate(payload_raw)

    with SessionLocal() as db:
        master_id = _get_single_master_id(db)

        master = db.get(Master, master_id)
        if master is None:
            not_found("Мастер не найден.", code="master_not_found")

        if not master.booking_enabled:
            conflict("Онлайн-запись временно недоступна.", code="booking_disabled")

        client_stmt = select(Client).where(
            Client.master_id == master_id,
            Client.telegram_id == data.telegram_id,
        )
        client = db.execute(client_stmt).scalars().first()

        if client is None:
            client = Client(
                master_id=master_id,
                telegram_id=data.telegram_id,
                name=data.name,
                phone=data.phone,
            )
            db.add(client)
            db.flush()

        if not client.booking_allowed:
            conflict("Для вас онлайн-запись недоступна. Свяжитесь с мастером.", code="client_blocked")

        service = db.get(Service, data.service_id)
        if service is None or not service.is_active:
            not_found("Услуга не найдена.", code="service_not_found")

        svc = AppointmentService(db)
        try:
            appointment = svc.create(
                master_id=master_id,
                client_id=client.id,
                service_id=service.id,
                datetime_start_utc=data.slot_start_utc,
            )
        except SlotBusyError:
            conflict(
                "Выбранный слот уже занят, обновите список свободного времени.",
                code="slot_busy",
            )

        item = AppointmentOut(
            id=appointment.id,
            service_name=service.name,
            datetime_start_utc=appointment.datetime_start,
            status=appointment.status,
            source=appointment.source,
        )

    return web.json_response(item.model_dump(mode="json"))


@routes.post("/api/miniapp/appointments/{appointment_id}/cancel")
async def cancel_appointment(request: web.Request) -> web.Response:
    """Cancel future appointment for current client."""
    telegram_id = get_telegram_id(request)
    appointment_id = parse_int("appointment_id", request.match_info.get("appointment_id"))

    with SessionLocal() as db:
        appt: Appointment | None = db.get(Appointment, appointment_id)
        if appt is None:
            not_found("Запись не найдена.", code="appointment_not_found")

        if appt.client is None or appt.client.telegram_id != telegram_id:
            forbidden("Вы не можете управлять этой записью.", code="not_your_appointment")

        now_utc = datetime.now(UTC)
        if appt.status != "confirmed" or appt.datetime_start <= now_utc:
            conflict("Эту запись уже нельзя отменить.", code="cannot_cancel")

        appt.status = "cancelled"
        db.add(appt)
        db.commit()
        db.refresh(appt)

        item = AppointmentOut(
            id=appt.id,
            service_name=appt.service.name,
            datetime_start_utc=appt.datetime_start,
            status=appt.status,
            source=appt.source,
        )

    return web.json_response(item.model_dump(mode="json"))


@routes.post("/api/miniapp/appointments/{appointment_id}/reschedule")
async def reschedule_appointment(request: web.Request) -> web.Response:
    """Reschedule existing appointment for current client."""
    telegram_id = get_telegram_id(request)
    appointment_id = parse_int("appointment_id", request.match_info.get("appointment_id"))
    payload_raw = await request.json()
    data = AppointmentRescheduleIn.model_validate(payload_raw)

    with SessionLocal() as db:
        appt: Appointment | None = db.get(Appointment, appointment_id)
        if appt is None:
            not_found("Запись не найдена.", code="appointment_not_found")

        if appt.client is None or appt.client.telegram_id != telegram_id:
            forbidden("Вы не можете управлять этой записью.", code="not_your_appointment")

        now_utc = datetime.now(UTC)
        if appt.status != "confirmed" or appt.datetime_start <= now_utc:
            conflict("Эту запись уже нельзя перенести.", code="cannot_reschedule")

        svc = AppointmentService(db)
        from bot.services.exceptions import SlotBusyError  # local import to avoid cycles

        try:
            appt = svc.reschedule(
                appointment_id=appointment_id,
                new_datetime_start_utc=data.slot_start_utc,
            )
        except SlotBusyError:
            conflict(
                "Выбранный слот уже занят, обновите список свободного времени.",
                code="slot_busy",
            )

        item = AppointmentOut(
            id=appt.id,
            service_name=appt.service.name,
            datetime_start_utc=appt.datetime_start,
            status=appt.status,
            source=appt.source,
        )

    return web.json_response(item.model_dump(mode="json"))


@routes.get("/api/miniapp/master/appointments")
async def get_master_appointments(request: web.Request) -> web.Response:
    """Return master's daily schedule (requires master/admin role)."""
    target_date = parse_date("date", request.query.get("date"))

    with SessionLocal() as db:
        master_id = require_master(db, request)
        master = db.get(Master, master_id)
        if master is None:
            not_found("Мастер не найден.", code="master_not_found")

        tz = ZoneInfo(master.timezone)
        day_start_local = datetime.combine(target_date, time(0, 0), tzinfo=tz)
        day_end_local = day_start_local + timedelta(days=1)

        day_start_utc = day_start_local.astimezone(UTC)
        day_end_utc = day_end_local.astimezone(UTC)

        stmt = (
            select(Appointment)
            .options(joinedload(Appointment.client), joinedload(Appointment.service))
            .where(
                Appointment.master_id == master_id,
                Appointment.status.in_(("confirmed", "completed", "no_show")),
                and_(
                    Appointment.datetime_start >= day_start_utc,
                    Appointment.datetime_start < day_end_utc,
                ),
            )
            .order_by(Appointment.datetime_start)
        )
        appointments = db.execute(stmt).scalars().all()

        items: list[MasterAppointmentOut] = []
        for appt in appointments:
            local_start = appt.datetime_start.astimezone(tz)
            items.append(
                MasterAppointmentOut(
                    id=appt.id,
                    client_name=appt.client.name if appt.client else "—",
                    client_phone=appt.client.phone if appt.client else None,
                    service_name=appt.service.name,
                    datetime_local=local_start,
                    status=appt.status,
                )
            )

    body = MasterAppointmentsResponse(
        date=target_date.isoformat(),
        appointments=items,
    )
    return web.json_response(body.model_dump(mode="json"))


def setup_routes(app: web.Application) -> None:
    """Attach mini-app routes to aiohttp application."""
    app.add_routes(routes)

