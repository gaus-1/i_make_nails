from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from aiohttp import web
from sqlalchemy import and_, func, select
from sqlalchemy.orm import joinedload

from bot.api.deps import (
    _get_single_master_id,
    conflict,
    forbidden,
    get_telegram_id_from_request,
    not_found,
    parse_date,
    parse_int,
    require_master,
    resolve_telegram_role,
)
from bot.api.schemas import (
    AppointmentCreateIn,
    AppointmentOut,
    AppointmentRescheduleIn,
    AppointmentsListResponse,
    BlockedSlotCreateIn,
    BlockedSlotOut,
    ClientOut,
    ClientPatchIn,
    ClientsListResponse,
    MasterAppointmentOut,
    MasterAppointmentsResponse,
    MasterSettingsOut,
    MasterSettingsPatchIn,
    MeOut,
    ServiceOut,
    ServicesResponse,
    SlotOut,
    SlotsResponse,
    WorkScheduleItemOut,
)
from bot.database import SessionLocal
from bot.models import Appointment, BlockedSlot, Client, Master, Service, WorkSchedule
from bot.services import AppointmentService, ScheduleService
from bot.services.exceptions import SlotBusyError

routes = web.RouteTableDef()


@routes.get("/api/miniapp/me")
async def get_me(request: web.Request) -> web.Response:
    """Return current user telegram_id and role (admin/master/client) for UI switcher."""
    telegram_id = get_telegram_id_from_request(request)
    role_raw = resolve_telegram_role(telegram_id)
    role = (role_raw or "client").lower()
    body = MeOut(telegram_id=telegram_id, role=role)
    return web.json_response(body.model_dump(mode="json"))


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
    telegram_id = get_telegram_id_from_request(request)

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
    """Create a new appointment for client in mini-app. telegram_id только из проверенного initData/header."""
    telegram_id = get_telegram_id_from_request(request)
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
            Client.telegram_id == telegram_id,
        )
        client = db.execute(client_stmt).scalars().first()

        if client is None:
            client = Client(
                master_id=master_id,
                telegram_id=telegram_id,
                name=data.name,
                phone=data.phone,
            )
            db.add(client)
            db.flush()

        if not client.booking_allowed:
            conflict(
                "Для вас онлайн-запись недоступна. Свяжитесь с мастером.", code="client_blocked"
            )

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
    telegram_id = get_telegram_id_from_request(request)
    appointment_id = parse_int("appointment_id", request.match_info.get("appointment_id"))

    with SessionLocal() as db:
        stmt = (
            select(Appointment)
            .options(joinedload(Appointment.client), joinedload(Appointment.service))
            .where(Appointment.id == appointment_id)
        )
        appt = db.execute(stmt).scalar_one_or_none()
        if appt is None:
            not_found("Запись не найдена.", code="appointment_not_found")

        if appt.client is None or appt.client.telegram_id != telegram_id:
            forbidden("Вы не можете управлять этой записью.", code="not_your_appointment")

        now_utc = datetime.now(UTC)
        start_utc = (
            appt.datetime_start
            if appt.datetime_start.tzinfo
            else appt.datetime_start.replace(tzinfo=UTC)
        )
        if appt.status != "confirmed" or start_utc <= now_utc:
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
    telegram_id = get_telegram_id_from_request(request)
    appointment_id = parse_int("appointment_id", request.match_info.get("appointment_id"))
    payload_raw = await request.json()
    data = AppointmentRescheduleIn.model_validate(payload_raw)

    with SessionLocal() as db:
        stmt = (
            select(Appointment)
            .options(joinedload(Appointment.client), joinedload(Appointment.service))
            .where(Appointment.id == appointment_id)
        )
        appt = db.execute(stmt).scalar_one_or_none()
        if appt is None:
            not_found("Запись не найдена.", code="appointment_not_found")

        if appt.client is None or appt.client.telegram_id != telegram_id:
            forbidden("Вы не можете управлять этой записью.", code="not_your_appointment")

        now_utc = datetime.now(UTC)
        start_utc = (
            appt.datetime_start
            if appt.datetime_start.tzinfo
            else appt.datetime_start.replace(tzinfo=UTC)
        )
        if appt.status != "confirmed" or start_utc <= now_utc:
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


@routes.get("/api/miniapp/master/clients")
async def get_master_clients(request: web.Request) -> web.Response:
    """Return list of clients for master (requires master/admin role)."""
    with SessionLocal() as db:
        master_id = require_master(db, request)

        now_utc = datetime.now(UTC)
        future_count_subq = (
            select(Appointment.client_id, func.count(Appointment.id).label("cnt"))
            .where(
                Appointment.master_id == master_id,
                Appointment.status == "confirmed",
                Appointment.datetime_start > now_utc,
            )
            .group_by(Appointment.client_id)
            .subquery()
        )

        stmt = select(Client).where(Client.master_id == master_id).order_by(Client.name, Client.id)
        clients = db.execute(stmt).scalars().all()

        items: list[ClientOut] = []
        for c in clients:
            future_count = (
                db.execute(
                    select(future_count_subq.c.cnt).where(future_count_subq.c.client_id == c.id)
                ).scalar_one_or_none()
                or 0
            )
            items.append(
                ClientOut(
                    id=c.id,
                    name=c.name,
                    phone=c.phone,
                    booking_allowed=c.booking_allowed,
                    future_appointments_count=future_count,
                )
            )

    body = ClientsListResponse(clients=items)
    return web.json_response(body.model_dump(mode="json"))


@routes.patch("/api/miniapp/master/clients/{client_id}")
async def patch_master_client(request: web.Request) -> web.Response:
    """Update client (e.g. blacklist booking_allowed). Requires master/admin."""
    client_id = parse_int("client_id", request.match_info.get("client_id"))
    payload_raw = await request.json() or {}
    data = ClientPatchIn.model_validate(payload_raw)

    with SessionLocal() as db:
        master_id = require_master(db, request)
        client = db.get(Client, client_id)
        if client is None or client.master_id != master_id:
            not_found("Клиент не найден.", code="client_not_found")

        if data.booking_allowed is not None:
            client.booking_allowed = data.booking_allowed
        db.add(client)
        db.commit()
        db.refresh(client)

        future_count = (
            db.execute(
                select(func.count(Appointment.id)).where(
                    Appointment.client_id == client.id,
                    Appointment.status == "confirmed",
                    Appointment.datetime_start > datetime.now(UTC),
                )
            ).scalar_one()
            or 0
        )

    item = ClientOut(
        id=client.id,
        name=client.name,
        phone=client.phone,
        booking_allowed=client.booking_allowed,
        future_appointments_count=future_count,
    )
    return web.json_response(item.model_dump(mode="json"))


@routes.get("/api/miniapp/master/settings")
async def get_master_settings(request: web.Request) -> web.Response:
    """Return master settings (booking_enabled, timezone, work_schedule). Requires master/admin."""
    with SessionLocal() as db:
        master_id = require_master(db, request)
        master = db.get(Master, master_id)
        if master is None:
            not_found("Мастер не найден.", code="master_not_found")

        ws_stmt = (
            select(WorkSchedule)
            .where(WorkSchedule.master_id == master_id)
            .order_by(WorkSchedule.day_of_week, WorkSchedule.time_start)
        )
        work_schedule = db.execute(ws_stmt).scalars().all()

    body = MasterSettingsOut(
        booking_enabled=master.booking_enabled,
        timezone=master.timezone,
        work_schedule=[WorkScheduleItemOut.model_validate(ws) for ws in work_schedule],
    )
    return web.json_response(body.model_dump(mode="json"))


@routes.patch("/api/miniapp/master/settings")
async def patch_master_settings(request: web.Request) -> web.Response:
    """Update master settings. Requires master/admin."""
    payload_raw = await request.json() or {}
    data = MasterSettingsPatchIn.model_validate(payload_raw)

    with SessionLocal() as db:
        master_id = require_master(db, request)
        master = db.get(Master, master_id)
        if master is None:
            not_found("Мастер не найден.", code="master_not_found")

        if data.booking_enabled is not None:
            master.booking_enabled = data.booking_enabled
        if data.timezone is not None:
            master.timezone = data.timezone
        if data.work_schedule is not None:
            existing_ws = (
                db.execute(select(WorkSchedule).where(WorkSchedule.master_id == master_id))
                .scalars()
                .all()
            )
            for ws_row in existing_ws:
                db.delete(ws_row)
            for item in data.work_schedule:
                ws = WorkSchedule(
                    master_id=master_id,
                    day_of_week=item.day_of_week,
                    time_start=item.time_start,
                    time_end=item.time_end,
                )
                db.add(ws)

        db.add(master)
        db.commit()
        db.refresh(master)

        ws_stmt = (
            select(WorkSchedule)
            .where(WorkSchedule.master_id == master_id)
            .order_by(WorkSchedule.day_of_week, WorkSchedule.time_start)
        )
        work_schedule = db.execute(ws_stmt).scalars().all()

    body = MasterSettingsOut(
        booking_enabled=master.booking_enabled,
        timezone=master.timezone,
        work_schedule=[WorkScheduleItemOut.model_validate(ws) for ws in work_schedule],
    )
    return web.json_response(body.model_dump(mode="json"))


@routes.get("/api/miniapp/master/blocked-slots")
async def get_master_blocked_slots(request: web.Request) -> web.Response:
    """Список блокировок мастера в диапазоне дат."""
    date_from = parse_date("date_from", request.query.get("date_from"))
    date_to = parse_date("date_to", request.query.get("date_to"))
    if date_to < date_from:
        conflict("date_to должен быть не раньше date_from.", code="invalid_range")

    with SessionLocal() as db:
        master_id = require_master(db, request)
        stmt = (
            select(BlockedSlot)
            .where(
                BlockedSlot.master_id == master_id,
                BlockedSlot.date_start <= date_to,
                BlockedSlot.date_end >= date_from,
            )
            .order_by(BlockedSlot.date_start)
        )
        slots = db.execute(stmt).scalars().all()
    items = [
        BlockedSlotOut(
            id=b.id,
            date_start=b.date_start,
            date_end=b.date_end,
            reason=b.reason,
        )
        for b in slots
    ]
    return web.json_response({"blocked_slots": [x.model_dump(mode="json") for x in items]})


@routes.post("/api/miniapp/master/blocked-slots")
async def post_master_blocked_slots(request: web.Request) -> web.Response:
    """Создать блокировку дат. date_end опционально — одна дата."""
    payload_raw = await request.json()
    data = BlockedSlotCreateIn.model_validate(payload_raw)
    date_end = data.date_end if data.date_end is not None else data.date_start
    if date_end < data.date_start:
        conflict("date_end не может быть раньше date_start.", code="invalid_range")

    with SessionLocal() as db:
        master_id = require_master(db, request)
        master = db.get(Master, master_id)
        if master is None:
            not_found("Мастер не найден.", code="master_not_found")
        tz = ZoneInfo(master.timezone)
        now_local = datetime.now(UTC).astimezone(tz).date()
        if date_end < now_local:
            conflict("Нельзя блокировать даты в прошлом.", code="past_date")

        blocked = BlockedSlot(
            master_id=master_id,
            date_start=data.date_start,
            date_end=date_end,
            reason=data.reason,
        )
        db.add(blocked)
        db.commit()
        db.refresh(blocked)
    item = BlockedSlotOut(
        id=blocked.id,
        date_start=blocked.date_start,
        date_end=blocked.date_end,
        reason=blocked.reason,
    )
    return web.json_response(item.model_dump(mode="json"))


@routes.delete("/api/miniapp/master/blocked-slots/{blocked_slot_id}")
async def delete_master_blocked_slot(request: web.Request) -> web.Response:
    """Удалить блокировку."""
    blocked_slot_id = parse_int("blocked_slot_id", request.match_info.get("blocked_slot_id"))

    with SessionLocal() as db:
        master_id = require_master(db, request)
        b = db.get(BlockedSlot, blocked_slot_id)
        if b is None or b.master_id != master_id:
            not_found("Блокировка не найдена.", code="blocked_slot_not_found")
        db.delete(b)
        db.commit()
    return web.Response(status=204)


def setup_routes(app: web.Application) -> None:
    """Attach mini-app routes to aiohttp application."""
    app.add_routes(routes)
