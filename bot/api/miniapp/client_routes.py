"""Маршруты мини-аппа для клиента: слоты, записи, создание/отмена/перенос."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aiohttp import web
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from bot.api.deps import (
    _get_single_master_id,
    conflict,
    forbidden,
    get_db,
    get_telegram_id_from_request,
    is_owner_telegram_id,
    not_found,
    parse_date,
    parse_int,
    resolve_telegram_role,
)
from bot.api.schemas import (
    AppointmentCreateIn,
    AppointmentOut,
    AppointmentRescheduleIn,
    AppointmentsListResponse,
    MeOut,
    SlotOut,
    SlotsResponse,
)
from bot.models import Appointment, Client, Master
from bot.services import AppointmentService, ScheduleService
from bot.services.exceptions import SlotBusyError

routes = web.RouteTableDef()


@routes.get("/api/miniapp/me")
async def get_me(request: web.Request) -> web.Response:
    """Текущий пользователь: telegram_id, роль и is_owner для переключателя в UI."""
    telegram_id = get_telegram_id_from_request(request)
    role_raw = resolve_telegram_role(telegram_id)
    role = (role_raw or "client").lower()
    is_owner = is_owner_telegram_id(telegram_id)
    body = MeOut(telegram_id=telegram_id, role=role, is_owner=is_owner)
    return web.json_response(body.model_dump(mode="json"))


@routes.get("/api/miniapp/slots")
async def get_free_slots(request: web.Request) -> web.Response:  # noqa: D401
    """Свободные слоты на дату (один мастер, длительность из настроек)."""
    target_date = parse_date("date", request.query.get("date"))

    with get_db() as db:
        master_id = _get_single_master_id(db)
        master = db.get(Master, master_id)
        if master is None:
            not_found("Мастер не найден.", code="master_not_found")

        schedule = ScheduleService(db)
        daily_slots = schedule.get_free_slots_for_date(
            master_id=master_id,
            target_date=target_date,
            duration_minutes=master.slot_duration_minutes,
        )
        slots = [SlotOut(start_utc_iso=slot.isoformat()) for slot in daily_slots.slots_utc]

    body = SlotsResponse(
        date=daily_slots.date.isoformat(),
        slots=slots,
        slot_duration_minutes=master.slot_duration_minutes,
    )
    return web.json_response(body.model_dump(mode="json"))


@routes.get("/api/miniapp/appointments/my")
async def get_my_appointments(request: web.Request) -> web.Response:
    """Return list of appointments for current client."""
    telegram_id = get_telegram_id_from_request(request)

    with get_db() as db:
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

        def _label(appt: Appointment) -> str:
            return appt.service.name if appt.service else "Запись"

        items = [
            AppointmentOut(
                id=appt.id,
                label=_label(appt),
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

    with get_db() as db:
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

        start_utc = data.slot_start_utc
        if start_utc.tzinfo is None:
            start_utc = start_utc.replace(tzinfo=UTC)
        if start_utc < datetime.now(UTC):
            conflict(
                "Нельзя записаться на прошедшую дату или время.",
                code="slot_in_past",
            )

        svc = AppointmentService(db)
        try:
            appointment = svc.create(
                master_id=master_id,
                client_id=client.id,
                datetime_start_utc=data.slot_start_utc,
            )
        except SlotBusyError:
            conflict(
                "Выбранный слот уже занят, обновите список свободного времени.",
                code="slot_busy",
            )

        item = AppointmentOut(
            id=appointment.id,
            label="Запись",
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

    with get_db() as db:
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

        label = appt.service.name if appt.service else "Запись"
        item = AppointmentOut(
            id=appt.id,
            label=label,
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

    with get_db() as db:
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

        label = appt.service.name if appt.service else "Запись"
        item = AppointmentOut(
            id=appt.id,
            label=label,
            datetime_start_utc=appt.datetime_start,
            status=appt.status,
            source=appt.source,
        )

    return web.json_response(item.model_dump(mode="json"))
