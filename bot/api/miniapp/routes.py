from __future__ import annotations

from datetime import date

from aiohttp import web
from sqlalchemy import select

from bot.database import SessionLocal
from bot.models import Master, Service
from bot.services import ScheduleService


routes = web.RouteTableDef()


def _get_single_master_id(db) -> int:
    """Return id of the single master in v1 or raise if not found."""
    master = db.execute(select(Master)).scalars().first()
    if master is None:
        msg = "Master record not found. Run onboarding first."
        raise web.HTTPBadRequest(text=msg)
    return master.id


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

        data = [
            {
                "id": svc.id,
                "name": svc.name,
                "duration_minutes": svc.duration_minutes,
            }
            for svc in services
        ]

    return web.json_response({"services": data})


@routes.get("/api/miniapp/slots")
async def get_free_slots(request: web.Request) -> web.Response:  # noqa: D401
    """Return free slots for a given date and service."""
    date_str = request.query.get("date")
    service_id_str = request.query.get("service_id")
    if not date_str or not service_id_str:
        raise web.HTTPBadRequest(text="Parameters 'date' and 'service_id' are required.")

    try:
        target_date = date.fromisoformat(date_str)
    except ValueError as exc:  # pragma: no cover - defensive
        msg = f"Invalid date format: {date_str}"
        raise web.HTTPBadRequest(text=msg) from exc

    try:
        service_id = int(service_id_str)
    except ValueError as exc:  # pragma: no cover - defensive
        msg = f"Invalid service_id: {service_id_str}"
        raise web.HTTPBadRequest(text=msg) from exc

    with SessionLocal() as db:
        service = db.get(Service, service_id)
        if service is None or not service.is_active:
            raise web.HTTPNotFound(text="Service not found.")

        master_id = service.master_id
        schedule = ScheduleService(db)
        daily_slots = schedule.get_free_slots_for_date(
            master_id=master_id,
            target_date=target_date,
            duration_minutes=service.duration_minutes,
        )

        data = [slot.isoformat() for slot in daily_slots.slots_utc]

    return web.json_response({"date": daily_slots.date.isoformat(), "slots": data})


def setup_routes(app: web.Application) -> None:
    """Attach mini-app routes to aiohttp application."""
    app.add_routes(routes)

