from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from bot.api.miniapp import client_routes, master_routes
from bot.api.miniapp.routes import setup_routes
from bot.config.settings import settings
from bot.models import Appointment, Base, Client, Master, Service, WorkSchedule


def create_test_app() -> web.Application:
    """Create aiohttp app with routes (DB patched via monkeypatch in tests)."""
    app = web.Application()
    setup_routes(app)
    return app


def setup_in_memory_session(monkeypatch: pytest.MonkeyPatch) -> Session:
    """Prepare in-memory SQLite DB and patch get_db in route modules to use it."""
    engine = create_engine("sqlite+pysqlite:///:memory:", echo=False, future=True)
    Base.metadata.create_all(bind=engine)
    test_session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    monkeypatch.setattr(client_routes, "get_db", test_session_factory)
    monkeypatch.setattr(master_routes, "get_db", test_session_factory)
    return test_session_factory()


def _patch_dev_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Включить dev-режим и задать master/admin Telegram ID для тестов."""
    monkeypatch.setattr(settings, "master_telegram_ids", "111")
    monkeypatch.setattr(settings, "admin_telegram_ids", "222")
    monkeypatch.setattr(settings, "miniapp_auth", "dev")


@pytest.mark.asyncio
async def test_full_client_flow_create_and_list_appointments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path: клиент получает слоты по дате, создаёт запись и видит её в /appointments/my."""
    db = setup_in_memory_session(monkeypatch)

    # настройка env: мастер и dev-режим (X-Telegram-Id без initData)
    monkeypatch.setattr(settings, "master_telegram_ids", "111")
    monkeypatch.setattr(settings, "admin_telegram_ids", "222")
    monkeypatch.setattr(settings, "miniapp_auth", "dev")

    master = Master(
        timezone="Europe/Moscow",
        booking_enabled=True,
        slot_duration_minutes=90,
    )
    db.add(master)
    db.flush()

    # рабочее время: понедельник 10:00-14:00 (дата в будущем, чтобы не срабатывал slot_in_past)
    today = date(2030, 2, 10)  # понедельник
    ws = WorkSchedule(
        master_id=master.id,
        day_of_week=today.weekday(),
        time_start=time(10, 0),
        time_end=time(14, 0),
    )
    db.add(ws)
    db.commit()

    app = create_test_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. получаем свободные слоты по дате
        resp = await client.get(
            "/api/miniapp/slots",
            params={"date": today.isoformat()},
        )
        assert resp.status == 200
        slots_payload = await resp.json()
        assert slots_payload["date"] == today.isoformat()
        assert slots_payload["slots"]
        first_slot_iso = slots_payload["slots"][0]["start_utc_iso"]

        # 2. создаём запись (telegram_id из заголовка в dev)
        telegram_id = 555
        resp = await client.post(
            "/api/miniapp/appointments",
            headers={"X-Telegram-Id": str(telegram_id)},
            json={
                "telegram_id": telegram_id,
                "name": "Тестовый клиент",
                "phone": "+79990000000",
                "slot_start_utc": first_slot_iso,
            },
        )
        assert resp.status == 200
        appointment_payload = await resp.json()
        assert appointment_payload["label"] == "Запись"

        # 3. клиент видит свою запись в /appointments/my
        resp = await client.get(
            "/api/miniapp/appointments/my",
            headers={"X-Telegram-Id": str(telegram_id)},
        )
        assert resp.status == 200
        my_payload = await resp.json()
        assert len(my_payload["appointments"]) == 1
        assert my_payload["appointments"][0]["label"] == "Запись"
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

    master = Master(
        timezone="Europe/Moscow",
        booking_enabled=True,
        slot_duration_minutes=90,
    )
    db.add(master)
    db.flush()

    client_model = Client(master_id=master.id, name="Клиент", phone=None, telegram_id=777)
    db.add(client_model)
    db.flush()

    # назначаем одну запись на сегодня (без услуги)
    today = date(2026, 2, 10)
    start_local = datetime(2026, 2, 10, 11, 0, tzinfo=UTC)
    appt = Appointment(
        master_id=master.id,
        client_id=client_model.id,
        service_id=None,
        datetime_start=start_local,
        datetime_end=start_local + timedelta(minutes=90),
        status="confirmed",
        source="test",
    )
    db.add(appt)
    db.commit()

    app = create_test_app()
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
        bad_body = await resp.json()
        assert bad_body.get("code") == "missing_telegram_id"

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
        assert payload["appointments"][0]["service_name"] == "Запись"
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

    app = create_test_app()
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

    app = create_test_app()
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
async def test_master_reschedule_appointment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Мастер переносит запись на новое время; не-мастер получает 403; занятый слот 409."""
    db = setup_in_memory_session(monkeypatch)
    monkeypatch.setattr(settings, "master_telegram_ids", "111")
    monkeypatch.setattr(settings, "admin_telegram_ids", "222")
    monkeypatch.setattr(settings, "miniapp_auth", "dev")

    master = Master(timezone="Europe/Moscow", booking_enabled=True, slot_duration_minutes=60)
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
    client_model = Client(master_id=master.id, telegram_id=555, name="Клиент", phone=None)
    db.add(client_model)
    db.flush()
    start_utc = datetime(2030, 2, 10, 8, 0, tzinfo=UTC)
    appt = Appointment(
        master_id=master.id,
        client_id=client_model.id,
        service_id=None,
        datetime_start=start_utc,
        datetime_end=start_utc + timedelta(minutes=60),
        status="confirmed",
        source="miniapp",
    )
    db.add(appt)
    db.commit()
    appt_id = appt.id
    new_slot_iso = "2030-02-10T11:00:00+00:00"

    app = create_test_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.patch(
            f"/api/miniapp/master/appointments/{appt_id}",
            headers={"X-Telegram-Id": "111"},
            json={"slot_start_utc": new_slot_iso},
        )
        assert resp.status == 200
        payload = await resp.json()
        assert (
            "2030-02-10" in payload["datetime_start_utc"] and "11" in payload["datetime_start_utc"]
        )

        resp = await client.patch(
            f"/api/miniapp/master/appointments/{appt_id}",
            headers={"X-Telegram-Id": "555"},
            json={"slot_start_utc": "2030-02-10T12:00:00+00:00"},
        )
        assert resp.status == 403

        start2 = datetime(2030, 2, 10, 10, 0, tzinfo=UTC)
        appt2 = Appointment(
            master_id=master.id,
            client_id=client_model.id,
            service_id=None,
            datetime_start=start2,
            datetime_end=start2 + timedelta(minutes=60),
            status="confirmed",
            source="miniapp",
        )
        db.add(appt2)
        db.commit()
        resp = await client.patch(
            f"/api/miniapp/master/appointments/{appt2.id}",
            headers={"X-Telegram-Id": "111"},
            json={"slot_start_utc": "2030-02-10T11:00:00+00:00"},
        )
        assert resp.status == 409
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

    app = create_test_app()
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

    app = create_test_app()
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
async def test_master_settings_patch_work_schedule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Мастер обновляет расписание работы (work_schedule); GET возвращает новые слоты."""
    db = setup_in_memory_session(monkeypatch)
    monkeypatch.setattr(settings, "master_telegram_ids", "111")
    monkeypatch.setattr(settings, "admin_telegram_ids", "222")
    monkeypatch.setattr(settings, "miniapp_auth", "dev")

    master = Master(timezone="Europe/Moscow", booking_enabled=True)
    db.add(master)
    db.commit()

    app = create_test_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        work_schedule = [
            {"day_of_week": 0, "time_start": "09:00:00", "time_end": "13:00:00"},
            {"day_of_week": 1, "time_start": "10:00:00", "time_end": "18:00:00"},
        ]
        resp = await client.patch(
            "/api/miniapp/master/settings",
            headers={"X-Telegram-Id": "111", "Content-Type": "application/json"},
            json={"work_schedule": work_schedule},
        )
        assert resp.status == 200
        payload = await resp.json()
        assert len(payload["work_schedule"]) == 2
        days = {ws["day_of_week"] for ws in payload["work_schedule"]}
        assert days == {0, 1}
        assert payload["work_schedule"][0]["time_start"] == "09:00:00"
        assert payload["work_schedule"][0]["time_end"] == "13:00:00"

        resp2 = await client.get(
            "/api/miniapp/master/settings",
            headers={"X-Telegram-Id": "111"},
        )
        assert resp2.status == 200
        assert len((await resp2.json())["work_schedule"]) == 2
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_auth_via_init_data_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prod: запрос только с X-Telegram-Init-Data (без X-Telegram-Id) даёт 200 и telegram_id из initData."""
    from bot.api import deps

    db = setup_in_memory_session(monkeypatch)
    monkeypatch.setattr(settings, "master_telegram_ids", "111")
    monkeypatch.setattr(settings, "admin_telegram_ids", "222")
    monkeypatch.setattr(settings, "miniapp_auth", "prod")

    master = Master(timezone="Europe/Moscow", booking_enabled=True)
    db.add(master)
    db.commit()

    def _mock_validate(_raw: str, _token: str, ttl_seconds: int = 86400) -> dict | None:
        return {"user": '{"id": 111}'}

    monkeypatch.setattr(deps, "validate_init_data", _mock_validate)

    app = create_test_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get(
            "/api/miniapp/me",
            headers={"X-Telegram-Init-Data": "any"},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["telegram_id"] == 111
        assert data["role"] == "master"
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

    app = create_test_app()
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


@pytest.mark.asyncio
async def test_me_returns_role(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /me возвращает telegram_id и role для клиента, мастера, админа."""
    db = setup_in_memory_session(monkeypatch)
    _patch_dev_auth(monkeypatch)
    db.add(Master(timezone="Europe/Moscow", booking_enabled=True))
    db.commit()

    app = create_test_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        resp = await client.get(
            "/api/miniapp/me",
            headers={"X-Telegram-Id": "555"},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["telegram_id"] == 555
        assert data["role"] == "client"

        resp = await client.get(
            "/api/miniapp/me",
            headers={"X-Telegram-Id": "111"},
        )
        assert resp.status == 200
        assert (await resp.json())["role"] == "master"

        resp = await client.get(
            "/api/miniapp/me",
            headers={"X-Telegram-Id": "222"},
        )
        assert resp.status == 200
        assert (await resp.json())["role"] == "admin"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_master_forbidden_for_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Клиент без прав мастера не может зайти в /master/* — 403."""
    db = setup_in_memory_session(monkeypatch)
    _patch_dev_auth(monkeypatch)
    db.add(Master(timezone="Europe/Moscow", booking_enabled=True))
    db.commit()

    app = create_test_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        resp = await client.get(
            "/api/miniapp/master/appointments",
            params={"date": "2026-02-10"},
            headers={"X-Telegram-Id": "555"},
        )
        assert resp.status == 403
        data = await resp.json()
        assert data.get("code") == "master_required"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_booking_disabled_409(monkeypatch: pytest.MonkeyPatch) -> None:
    """При booking_enabled=False создание записи возвращает 409."""
    db = setup_in_memory_session(monkeypatch)
    _patch_dev_auth(monkeypatch)
    master = Master(
        timezone="Europe/Moscow",
        booking_enabled=False,
        slot_duration_minutes=60,
    )
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
    db.commit()

    app = create_test_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        resp = await client.post(
            "/api/miniapp/appointments",
            headers={"X-Telegram-Id": "555"},
            json={
                "telegram_id": 555,
                "name": "Клиент",
                "phone": None,
                "slot_start_utc": "2026-02-10T10:00:00+00:00",
            },
        )
        assert resp.status == 409
        data = await resp.json()
        assert data.get("code") == "booking_disabled"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_client_blocked_409(monkeypatch: pytest.MonkeyPatch) -> None:
    """При booking_allowed=False создание записи возвращает 409."""
    db = setup_in_memory_session(monkeypatch)
    _patch_dev_auth(monkeypatch)
    master = Master(
        timezone="Europe/Moscow",
        booking_enabled=True,
        slot_duration_minutes=60,
    )
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
    client_model = Client(
        master_id=master.id,
        telegram_id=555,
        name="Клиент",
        phone=None,
        booking_allowed=False,
    )
    db.add(client_model)
    db.commit()

    app = create_test_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        resp = await client.post(
            "/api/miniapp/appointments",
            headers={"X-Telegram-Id": "555"},
            json={
                "telegram_id": 555,
                "name": "Клиент",
                "phone": None,
                "slot_start_utc": "2026-02-10T10:00:00+00:00",
            },
        )
        assert resp.status == 409
        data = await resp.json()
        assert data.get("code") == "client_blocked"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_slots_invalid_date_400(monkeypatch: pytest.MonkeyPatch) -> None:
    """Слоты с невалидным date возвращают 400."""
    db = setup_in_memory_session(monkeypatch)
    _patch_dev_auth(monkeypatch)
    db.add(Master(timezone="Europe/Moscow", booking_enabled=True))
    db.commit()

    app = create_test_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        resp = await client.get(
            "/api/miniapp/slots",
            params={"date": "invalid"},
            headers={"X-Telegram-Id": "555"},
        )
        assert resp.status == 400
        data = await resp.json()
        assert data.get("code") == "invalid_date"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_slots_missing_date_400(monkeypatch: pytest.MonkeyPatch) -> None:
    """Слоты без параметра date возвращают 400."""
    db = setup_in_memory_session(monkeypatch)
    _patch_dev_auth(monkeypatch)
    db.add(Master(timezone="Europe/Moscow", booking_enabled=True))
    db.commit()

    app = create_test_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        resp = await client.get(
            "/api/miniapp/slots",
            headers={"X-Telegram-Id": "555"},
        )
        assert resp.status == 400
        data = await resp.json()
        assert "error" in data and "code" in data
        assert data.get("code") == "missing_parameter"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_create_appointment_slot_busy_409(monkeypatch: pytest.MonkeyPatch) -> None:
    """Создание записи в занятый слот возвращает 409."""
    db = setup_in_memory_session(monkeypatch)
    _patch_dev_auth(monkeypatch)
    master = Master(
        timezone="Europe/Moscow",
        booking_enabled=True,
        slot_duration_minutes=60,
    )
    db.add(master)
    db.flush()
    today = date(2030, 2, 10)  # в будущем, иначе API вернёт slot_in_past
    ws = WorkSchedule(
        master_id=master.id,
        day_of_week=today.weekday(),
        time_start=time(10, 0),
        time_end=time(14, 0),
    )
    db.add(ws)
    client_model = Client(master_id=master.id, telegram_id=555, name="Клиент", phone=None)
    db.add(client_model)
    db.flush()
    slot_start = datetime(2030, 2, 10, 10, 0, tzinfo=UTC)
    existing = Appointment(
        master_id=master.id,
        client_id=client_model.id,
        service_id=None,
        datetime_start=slot_start,
        datetime_end=slot_start + timedelta(minutes=60),
        status="confirmed",
        source="miniapp",
    )
    db.add(existing)
    db.commit()

    app = create_test_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        resp = await client.post(
            "/api/miniapp/appointments",
            headers={"X-Telegram-Id": "555"},
            json={
                "telegram_id": 555,
                "name": "Другой",
                "phone": None,
                "slot_start_utc": "2030-02-10T10:00:00+00:00",
            },
        )
        assert resp.status == 409
        data = await resp.json()
        assert data.get("code") == "slot_busy"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_cancel_not_own_appointment_403(monkeypatch: pytest.MonkeyPatch) -> None:
    """Клиент не может отменить чужую запись — 403."""
    db = setup_in_memory_session(monkeypatch)
    _patch_dev_auth(monkeypatch)
    master = Master(timezone="Europe/Moscow", booking_enabled=True)
    db.add(master)
    db.flush()
    client_owner = Client(master_id=master.id, telegram_id=111, name="Владелец", phone=None)
    client_other = Client(master_id=master.id, telegram_id=999, name="Чужой", phone=None)
    db.add(client_owner)
    db.add(client_other)
    db.flush()
    start_utc = datetime(2030, 2, 10, 10, 0, tzinfo=UTC)
    appt = Appointment(
        master_id=master.id,
        client_id=client_owner.id,
        service_id=None,
        datetime_start=start_utc,
        datetime_end=start_utc + timedelta(minutes=60),
        status="confirmed",
        source="miniapp",
    )
    db.add(appt)
    db.commit()
    appt_id = appt.id

    app = create_test_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        resp = await client.post(
            f"/api/miniapp/appointments/{appt_id}/cancel",
            headers={"X-Telegram-Id": "999"},
        )
        assert resp.status == 403
        data = await resp.json()
        assert data.get("code") == "not_your_appointment"
    finally:
        await client.close()
