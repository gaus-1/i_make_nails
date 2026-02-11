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

    # настройка env: мастер и dev-режим (X-Telegram-Id без initData)
    monkeypatch.setattr(settings, "master_telegram_ids", "111")
    monkeypatch.setattr(settings, "admin_telegram_ids", "222")
    monkeypatch.setattr(settings, "miniapp_auth", "dev")

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

        # 3. создаём запись (telegram_id из заголовка в dev)
        telegram_id = 555
        resp = await client.post(
            "/api/miniapp/appointments",
            headers={"X-Telegram-Id": str(telegram_id)},
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
    monkeypatch.setattr(settings, "miniapp_auth", "dev")

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


@pytest.mark.asyncio
async def test_cancel_appointment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Клиент отменяет подтверждённую запись; после отмены запись не в /my (cancelled исключаются)."""
    db = setup_in_memory_session(monkeypatch)
    monkeypatch.setattr(settings, "master_telegram_ids", "111")
    monkeypatch.setattr(settings, "admin_telegram_ids", "222")
    monkeypatch.setattr(settings, "miniapp_auth", "dev")

    master = Master(timezone="Europe/Moscow", booking_enabled=True)
    db.add(master)
    db.flush()
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
        name="Маникюр",
        duration_minutes=60,
        price_rub=None,
        is_active=True,
        sort_order=0,
    )
    db.add(service)
    db.flush()
    client_model = Client(master_id=master.id, telegram_id=555, name="Клиент", phone=None)
    db.add(client_model)
    db.flush()
    start_utc = datetime(2030, 2, 10, 8, 0, tzinfo=UTC)
    appt = Appointment(
        master_id=master.id,
        client_id=client_model.id,
        service_id=service.id,
        datetime_start=start_utc,
        datetime_end=start_utc + timedelta(minutes=60),
        status="confirmed",
        source="miniapp",
    )
    db.add(appt)
    db.commit()
    appt_id = appt.id

    app = create_test_app(db)
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.post(
            f"/api/miniapp/appointments/{appt_id}/cancel",
            headers={"X-Telegram-Id": "555"},
        )
        assert resp.status == 200
        payload = await resp.json()
        assert payload["status"] == "cancelled"

        resp = await client.get(
            "/api/miniapp/appointments/my",
            headers={"X-Telegram-Id": "555"},
        )
        assert resp.status == 200
        my_payload = await resp.json()
        assert len(my_payload["appointments"]) == 0
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_reschedule_appointment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Клиент переносит запись на новый слот."""
    db = setup_in_memory_session(monkeypatch)
    monkeypatch.setattr(settings, "master_telegram_ids", "111")
    monkeypatch.setattr(settings, "admin_telegram_ids", "222")
    monkeypatch.setattr(settings, "miniapp_auth", "dev")

    master = Master(timezone="Europe/Moscow", booking_enabled=True)
    db.add(master)
    db.flush()
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
        name="Маникюр",
        duration_minutes=60,
        price_rub=None,
        is_active=True,
        sort_order=0,
    )
    db.add(service)
    db.flush()
    client_model = Client(master_id=master.id, telegram_id=555, name="Клиент", phone=None)
    db.add(client_model)
    db.flush()
    start_utc = datetime(2030, 2, 10, 8, 0, tzinfo=UTC)
    appt = Appointment(
        master_id=master.id,
        client_id=client_model.id,
        service_id=service.id,
        datetime_start=start_utc,
        datetime_end=start_utc + timedelta(minutes=60),
        status="confirmed",
        source="miniapp",
    )
    db.add(appt)
    db.commit()
    appt_id = appt.id
    new_slot_iso = "2030-02-10T11:00:00+00:00"

    app = create_test_app(db)
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.post(
            f"/api/miniapp/appointments/{appt_id}/reschedule",
            headers={"X-Telegram-Id": "555"},
            json={"slot_start_utc": new_slot_iso},
        )
        assert resp.status == 200
        payload = await resp.json()
        assert (
            "2030-02-10T11:00:00" in payload["datetime_start_utc"]
            or "11:00" in payload["datetime_start_utc"]
        )

        resp = await client.get(
            "/api/miniapp/appointments/my",
            headers={"X-Telegram-Id": "555"},
        )
        assert resp.status == 200
        my_payload = await resp.json()
        assert len(my_payload["appointments"]) == 1
        assert (
            "11:00" in my_payload["appointments"][0]["datetime_start_utc"]
            or "11" in my_payload["appointments"][0]["datetime_start_utc"]
        )
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_master_clients_get_and_patch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Мастер получает список клиентов и меняет booking_allowed."""
    db = setup_in_memory_session(monkeypatch)
    monkeypatch.setattr(settings, "master_telegram_ids", "111")
    monkeypatch.setattr(settings, "admin_telegram_ids", "222")
    monkeypatch.setattr(settings, "miniapp_auth", "dev")

    master = Master(timezone="Europe/Moscow", booking_enabled=True)
    db.add(master)
    db.flush()
    client_model = Client(
        master_id=master.id, telegram_id=777, name="Иван", phone="+7999", booking_allowed=True
    )
    db.add(client_model)
    db.commit()

    app = create_test_app(db)
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get(
            "/api/miniapp/master/clients",
            headers={"X-Telegram-Id": "111"},
        )
        assert resp.status == 200
        payload = await resp.json()
        assert len(payload["clients"]) == 1
        assert payload["clients"][0]["booking_allowed"] is True
        cid = payload["clients"][0]["id"]

        resp = await client.patch(
            f"/api/miniapp/master/clients/{cid}",
            headers={"X-Telegram-Id": "111", "Content-Type": "application/json"},
            json={"booking_allowed": False},
        )
        assert resp.status == 200
        payload2 = await resp.json()
        assert payload2["booking_allowed"] is False

        resp = await client.get(
            "/api/miniapp/master/clients",
            headers={"X-Telegram-Id": "111"},
        )
        assert resp.status == 200
        assert (await resp.json())["clients"][0]["booking_allowed"] is False
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_master_settings_get_and_patch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Мастер получает настройки и обновляет booking_enabled и timezone."""
    db = setup_in_memory_session(monkeypatch)
    monkeypatch.setattr(settings, "master_telegram_ids", "111")
    monkeypatch.setattr(settings, "admin_telegram_ids", "222")
    monkeypatch.setattr(settings, "miniapp_auth", "dev")

    master = Master(timezone="Europe/Moscow", booking_enabled=True)
    db.add(master)
    db.commit()

    app = create_test_app(db)
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get(
            "/api/miniapp/master/settings",
            headers={"X-Telegram-Id": "111"},
        )
        assert resp.status == 200
        payload = await resp.json()
        assert payload["booking_enabled"] is True
        assert payload["timezone"] == "Europe/Moscow"

        resp = await client.patch(
            "/api/miniapp/master/settings",
            headers={"X-Telegram-Id": "111", "Content-Type": "application/json"},
            json={"booking_enabled": False},
        )
        assert resp.status == 200
        assert (await resp.json())["booking_enabled"] is False

        resp = await client.patch(
            "/api/miniapp/master/settings",
            headers={"X-Telegram-Id": "111", "Content-Type": "application/json"},
            json={"timezone": "Asia/Yekaterinburg"},
        )
        assert resp.status == 200
        assert (await resp.json())["timezone"] == "Asia/Yekaterinburg"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_blocked_slots_get_post_delete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Мастер: пустой список блокировок, создание, удаление."""
    db = setup_in_memory_session(monkeypatch)
    monkeypatch.setattr(settings, "master_telegram_ids", "111")
    monkeypatch.setattr(settings, "admin_telegram_ids", "222")
    monkeypatch.setattr(settings, "miniapp_auth", "dev")

    master = Master(timezone="Europe/Moscow", booking_enabled=True)
    db.add(master)
    db.commit()

    app = create_test_app(db)
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get(
            "/api/miniapp/master/blocked-slots",
            params={"date_from": "2026-02-01", "date_to": "2026-02-28"},
            headers={"X-Telegram-Id": "111"},
        )
        assert resp.status == 200
        payload = await resp.json()
        assert payload["blocked_slots"] == []

        resp = await client.post(
            "/api/miniapp/master/blocked-slots",
            headers={"X-Telegram-Id": "111", "Content-Type": "application/json"},
            json={"date_start": "2026-02-15", "reason": "Выходной"},
        )
        assert resp.status == 200
        created = await resp.json()
        bid = created["id"]
        assert created["date_start"] == "2026-02-15"
        assert created["date_end"] == "2026-02-15"
        assert created["reason"] == "Выходной"

        resp = await client.get(
            "/api/miniapp/master/blocked-slots",
            params={"date_from": "2026-02-01", "date_to": "2026-02-28"},
            headers={"X-Telegram-Id": "111"},
        )
        assert resp.status == 200
        assert len((await resp.json())["blocked_slots"]) == 1

        resp = await client.delete(
            f"/api/miniapp/master/blocked-slots/{bid}",
            headers={"X-Telegram-Id": "111"},
        )
        assert resp.status == 204

        resp = await client.get(
            "/api/miniapp/master/blocked-slots",
            params={"date_from": "2026-02-01", "date_to": "2026-02-28"},
            headers={"X-Telegram-Id": "111"},
        )
        assert resp.status == 200
        assert (await resp.json())["blocked_slots"] == []
    finally:
        await client.close()
