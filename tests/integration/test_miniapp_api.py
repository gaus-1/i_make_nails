from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from bot.api.miniapp import routes as routes_module
from bot.api.miniapp.routes import setup_routes
from bot.config.settings import settings
from bot.models import Appointment, Base, Client, Master, Service, WorkSchedule


def create_test_app(db: Session) -> web.Application:
    """Create aiohttp app wired to a given SQLAlchemy session."""
    app = web.Application()
    setup_routes(app)
    return app


def setup_in_memory_session(monkeypatch: pytest.MonkeyPatch) -> Session:
    """Prepare in-memory SQLite DB and patch SessionLocal to use it."""
    engine = create_engine("sqlite+pysqlite:///:memory:", echo=False, future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    # patch SessionLocal used by API handlers in miniapp.routes
    monkeypatch.setattr(routes_module, "SessionLocal", SessionLocal, raising=False)

    return SessionLocal()


@pytest.mark.asyncio
async def test_full_client_flow_create_and_list_appointments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path: клиент получает услуги, слоты, создаёт запись и видит её в /appointments/my."""
    db = setup_in_memory_session(monkeypatch)

    # настройка env-подобных настроек для мастера
    monkeypatch.setattr(settings, "master_telegram_ids", "111")
    monkeypatch.setattr(settings, "admin_telegram_ids", "222")

    master = Master(timezone="Europe/Moscow", booking_enabled=True)
    db.add(master)
    db.flush()

    # рабочее время: сегодня 10:00-14:00
    today = date(2026, 2, 10)
    ws = WorkSchedule(
        master_id=master.id,
        day_of_week=today.weekday(),
        time_start=time(10, 0),
        time_end=time(14, 0),
    )
    db.add(ws)

    service = Service(
        master_id=master.id,
        name="Аппаратный маникюр",
        duration_minutes=90,
        price_rub=None,
        is_active=True,
        sort_order=0,
    )
    db.add(service)
    db.commit()

    app = create_test_app(db)
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. получаем услуги
        resp = await client.get("/api/miniapp/services")
        assert resp.status == 200
        services_payload = await resp.json()
        assert services_payload["services"][0]["name"] == "Аппаратный маникюр"
        service_id = services_payload["services"][0]["id"]

        # 2. получаем свободные слоты
        resp = await client.get(
            "/api/miniapp/slots",
            params={"date": today.isoformat(), "service_id": str(service_id)},
        )
        assert resp.status == 200
        slots_payload = await resp.json()
        assert slots_payload["date"] == today.isoformat()
        assert slots_payload["slots"]
        first_slot_iso = slots_payload["slots"][0]["start_utc_iso"]

        # 3. создаём запись
        telegram_id = 555
        resp = await client.post(
            "/api/miniapp/appointments",
            json={
                "telegram_id": telegram_id,
                "name": "Тестовый клиент",
                "phone": "+79990000000",
                "service_id": service_id,
                "slot_start_utc": first_slot_iso,
            },
        )
        assert resp.status == 200
        appointment_payload = await resp.json()
        assert appointment_payload["service_name"] == "Аппаратный маникюр"

        # 4. клиент видит свою запись в /appointments/my
        resp = await client.get(
            "/api/miniapp/appointments/my",
            headers={"X-Telegram-Id": str(telegram_id)},
        )
        assert resp.status == 200
        my_payload = await resp.json()
        assert len(my_payload["appointments"]) == 1
        assert my_payload["appointments"][0]["service_name"] == "Аппаратный маникюр"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_master_daily_schedule_shows_confirmed_appointments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Мастер видит расписание дня, недоступен без master/admin Telegram ID."""
    db = setup_in_memory_session(monkeypatch)

    monkeypatch.setattr(settings, "master_telegram_ids", "111")
    monkeypatch.setattr(settings, "admin_telegram_ids", "222")

    master = Master(timezone="Europe/Moscow", booking_enabled=True)
    db.add(master)
    db.flush()

    client_model = Client(master_id=master.id, name="Клиент", phone=None, telegram_id=777)
    db.add(client_model)

    service = Service(master_id=master.id, name="Комбинированный маникюр", duration_minutes=120)
    db.add(service)
    db.flush()

    # назначаем одну запись на сегодня
    today = date(2026, 2, 10)
    start_local = datetime(2026, 2, 10, 11, 0, tzinfo=UTC)
    appt = Appointment(
        master_id=master.id,
        client_id=client_model.id,
        service_id=service.id,
        datetime_start=start_local,
        datetime_end=start_local + timedelta(minutes=120),
        status="confirmed",
        source="test",
    )
    db.add(appt)
    db.commit()

    app = create_test_app(db)
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # без Telegram ID мастера вернётся 400 (нет telegram_id)
        resp = await client.get(
            "/api/miniapp/master/appointments",
            params={"date": today.isoformat()},
        )
        assert resp.status == 400

        # с Telegram ID мастера
        resp = await client.get(
            "/api/miniapp/master/appointments",
            params={"date": today.isoformat()},
            headers={"X-Telegram-Id": "111"},
        )
        assert resp.status == 200
        payload = await resp.json()
        assert payload["date"] == today.isoformat()
        assert len(payload["appointments"]) == 1
        assert payload["appointments"][0]["service_name"] == "Комбинированный маникюр"
    finally:
        await client.close()
