"""Маршруты мини-аппа для мастера: расписание, клиенты, настройки, блокировки."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from aiohttp import web
from sqlalchemy import and_, func, select
from sqlalchemy.orm import joinedload

from bot.api.deps import (
    conflict,
    get_db,
    not_found,
    parse_date,
    parse_int,
    require_master,
)
from bot.api.schemas import (
    BlockedSlotCreateIn,
    BlockedSlotOut,
    ClientOut,
    ClientPatchIn,
    ClientsListResponse,
    MasterAppointmentOut,
    MasterAppointmentsResponse,
    MasterSettingsOut,
    MasterSettingsPatchIn,
    WorkScheduleItemOut,
)
from bot.models import Appointment, BlockedSlot, Client, Master, WorkSchedule

routes = web.RouteTableDef()


@routes.get("/api/miniapp/master/appointments")
async def get_master_appointments(request: web.Request) -> web.Response:
    """Return master's schedule for a day or date range (requires master/admin role)."""
    target_date = parse_date("date", request.query.get("date"))
    date_to_str = request.query.get("date_to")
    end_date = parse_date("date_to", date_to_str) if date_to_str else target_date
    if end_date < target_date:
        end_date = target_date

    with get_db() as db:
        master_id = require_master(db, request)
        master = db.get(Master, master_id)
        if master is None:
            not_found("Мастер не найден.", code="master_not_found")

        tz = ZoneInfo(master.timezone)
        day_start_local = datetime.combine(target_date, time(0, 0), tzinfo=tz)
        day_end_local = datetime.combine(end_date, time(0, 0), tzinfo=tz) + timedelta(days=1)

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
                    client_telegram_id=appt.client.telegram_id if appt.client else None,
                    service_name=appt.service.name if appt.service else "Запись",
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
    with get_db() as db:
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
                    telegram_id=c.telegram_id,
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

    with get_db() as db:
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
    with get_db() as db:
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

    with get_db() as db:
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
        slot_duration_minutes=master.slot_duration_minutes,
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

    with get_db() as db:
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

    with get_db() as db:
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

    with get_db() as db:
        master_id = require_master(db, request)
        b = db.get(BlockedSlot, blocked_slot_id)
        if b is None or b.master_id != master_id:
            not_found("Блокировка не найдена.", code="blocked_slot_not_found")
        db.delete(b)
        db.commit()
    return web.Response(status=204)
