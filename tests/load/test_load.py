"""Нагрузочные тесты API: параллельные запросы к основным эндпоинтам."""

from __future__ import annotations

import asyncio
import time
from datetime import time as dt_time

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bot.api.miniapp import client_routes, master_routes
from bot.api.miniapp.routes import setup_routes
from bot.config.settings import settings
from bot.models import Base, Master, WorkSchedule


@pytest.fixture
def load_test_app(monkeypatch: pytest.MonkeyPatch) -> web.Application:
    """Приложение с in-memory БД для нагрузочных тестов."""
    engine = create_engine("sqlite+pysqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    with session_factory() as db:
        master = Master(
            timezone="Europe/Moscow",
            booking_enabled=True,
            slot_duration_minutes=60,
        )
        db.add(master)
        db.flush()
        for d in range(7):
            db.add(
                WorkSchedule(
                    master_id=master.id,
                    day_of_week=d,
                    time_start=dt_time(9, 0),
                    time_end=dt_time(18, 0),
                )
            )
        db.commit()

    monkeypatch.setattr(settings, "master_telegram_ids", "111")
    monkeypatch.setattr(settings, "admin_telegram_ids", "222")
    monkeypatch.setattr(settings, "miniapp_auth", "dev")
    monkeypatch.setattr(client_routes, "get_db", session_factory)
    monkeypatch.setattr(master_routes, "get_db", session_factory)

    app = web.Application()
    setup_routes(app)
    return app


@pytest.mark.asyncio
async def test_concurrent_slots_requests(load_test_app: web.Application) -> None:
    """50 параллельных запросов /slots — все 200, < 2 сек."""
    server = TestServer(load_test_app)
    client = TestClient(server)
    await client.start_server()

    try:
        n = 50
        headers = {"X-Telegram-Id": "555"}
        params = {"date": "2026-02-10"}

        async def fetch():
            return await client.get(
                "/api/miniapp/slots",
                params=params,
                headers=headers,
            )

        start = time.perf_counter()
        tasks = [fetch() for _ in range(n)]
        results = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start

        statuses = [r.status for r in results]
        assert all(s == 200 for s in statuses), f"Expected all 200, got: {statuses[:10]}..."
        assert elapsed < 2.0, f"{n} requests took {elapsed:.2f}s (expected < 2s)"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_concurrent_me_requests(load_test_app: web.Application) -> None:
    """100 параллельных запросов /me — все 200."""
    server = TestServer(load_test_app)
    client = TestClient(server)
    await client.start_server()

    try:
        n = 100
        headers = {"X-Telegram-Id": "555"}

        async def fetch():
            return await client.get("/api/miniapp/me", headers=headers)

        tasks = [fetch() for _ in range(n)]
        results = await asyncio.gather(*tasks)
        statuses = [r.status for r in results]
        assert all(s == 200 for s in statuses)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_concurrent_master_appointments(load_test_app: web.Application) -> None:
    """30 параллельных запросов master/appointments — все 200."""
    server = TestServer(load_test_app)
    client = TestClient(server)
    await client.start_server()

    try:
        n = 30
        headers = {"X-Telegram-Id": "111"}
        params = {"date": "2026-02-10"}

        async def fetch():
            return await client.get(
                "/api/miniapp/master/appointments",
                params=params,
                headers=headers,
            )

        tasks = [fetch() for _ in range(n)]
        results = await asyncio.gather(*tasks)
        statuses = [r.status for r in results]
        assert all(s == 200 for s in statuses)
    finally:
        await client.close()
