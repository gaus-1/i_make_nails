"""Точка входа HTTP: aiohttp, API мини-аппа, раздача статики. При E2E_SERVER=1 бот не поднимается."""

import asyncio
import os
import subprocess
import sys
from collections.abc import Awaitable, Callable
from datetime import time
from pathlib import Path

from aiohttp import web
from loguru import logger
from sqlalchemy import select

from bot.api.deps import get_db
from bot.api.miniapp.routes import setup_routes as setup_miniapp_routes
from bot.config.settings import settings
from bot.models import Master, WorkSchedule


def _run_migrations() -> None:
    """Применить миграции Alembic перед стартом (для Railway и др.)."""
    root = Path(__file__).resolve().parent
    env = os.environ.copy()
    env.setdefault("DATABASE_URL", settings.database_url)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        logger.error("alembic upgrade head failed: {} {}", result.stdout, result.stderr)
        raise SystemExit(result.returncode)
    if result.stdout.strip():
        logger.info("Migrations: {}", result.stdout.strip())


def _ensure_single_master() -> None:
    """Если в БД нет ни одного мастера — создать одного с дефолтным расписанием (для прода)."""
    with get_db() as db:
        if db.execute(select(Master).limit(1)).scalars().first() is not None:
            return
        master = Master(
            timezone="Europe/Moscow",
            booking_enabled=True,
            slot_duration_minutes=120,
        )
        db.add(master)
        db.flush()
        for day in range(7):
            db.add(
                WorkSchedule(
                    master_id=master.id,
                    day_of_week=day,
                    time_start=time(9, 0),
                    time_end=time(18, 0),
                )
            )
        db.commit()
    logger.info("Created default master record")


def _normalize_webhook_domain(raw: str) -> str:
    """Убрать протокол и путь из WEBHOOK_DOMAIN, оставить только хост."""
    s = raw.strip().rstrip("/")
    for prefix in ("https://", "http://"):
        if s.lower().startswith(prefix):
            s = s[len(prefix) :].strip().rstrip("/")
            break
    if "/" in s:
        s = s.split("/", 1)[0]
    return s


@web.middleware
async def json_error_middleware(
    request: web.Request,
    handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
) -> web.StreamResponse:
    """Необработанные исключения — ответ 500 в формате JSON."""
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unhandled error: {}", exc)
        return web.json_response(
            {"error": "Internal server error.", "code": "internal_error"},
            status=500,
        )


async def create_app() -> web.Application:
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(str(log_dir / "app.log"), rotation="10 MB")

    app = web.Application(middlewares=[json_error_middleware])

    # Health endpoint
    async def health(request: web.Request) -> web.Response:  # noqa: ANN001
        return web.Response(text="ok")

    app.router.add_get("/health", health)

    # Mini-app HTTP API routes
    setup_miniapp_routes(app)

    # В режиме E2E не поднимаем бота (не нужен валидный TELEGRAM_BOT_TOKEN)
    if os.environ.get("E2E_SERVER") != "1":
        try:
            from aiogram import Bot, Dispatcher
            from aiogram.utils.token import TokenValidationError
            from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

            from bot.handlers import start_router

            async def on_startup(bot: Bot) -> None:
                host = _normalize_webhook_domain(settings.webhook_domain)
                if not host:
                    raise ValueError("WEBHOOK_DOMAIN пустой или неверный")
                webhook_url = f"https://{host}/webhook"
                logger.info("Setting webhook: {}", webhook_url)
                await bot.set_webhook(webhook_url, drop_pending_updates=True)
                logger.info("Webhook set successfully")

            bot = Bot(token=settings.telegram_bot_token)
            dp = Dispatcher()
            dp.include_router(start_router)
            dp.startup.register(on_startup)

            webhook_path = "/webhook"
            SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=webhook_path)
            setup_application(app, dp, bot=bot)
        except TokenValidationError:
            if settings.miniapp_auth == "dev":
                logger.warning(
                    "Telegram token invalid; running without bot. Mini-app API and static only."
                )
            else:
                raise

    # Статика мини-приложения (собранный frontend из Docker)
    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.exists():
        index_path = static_dir / "index.html"

        async def index(_request: web.Request) -> web.StreamResponse:
            return web.FileResponse(index_path)

        app.router.add_get("/", index)
        app.router.add_static("/assets", str(static_dir / "assets"))
        # Иконка и прочие файлы из корня dist (например /vite.svg)
        app.router.add_static("/", str(static_dir), name="static_root")
    else:

        async def no_static(_request: web.Request) -> web.Response:
            return web.Response(text="Mini-app not built.", status=404)

        app.router.add_get("/", no_static)

    return app


def _seed_e2e_db() -> None:
    """Очистить данные и заполнить БД для E2E: один мастер, расписание. Схема из миграций."""
    from datetime import time

    from sqlalchemy import delete
    from sqlalchemy.orm import Session

    from bot.database.engine import SessionLocal
    from bot.models import Appointment, BlockedSlot, Client, Master, Service, WorkSchedule

    db: Session = SessionLocal()
    try:
        db.execute(delete(Appointment))
        db.execute(delete(BlockedSlot))
        db.execute(delete(WorkSchedule))
        db.execute(delete(Service))
        db.execute(delete(Client))
        db.execute(delete(Master))
        db.commit()

        master = Master(
            timezone="Europe/Moscow",
            booking_enabled=True,
            slot_duration_minutes=120,
        )
        db.add(master)
        db.flush()
        for day in range(7):
            db.add(
                WorkSchedule(
                    master_id=master.id,
                    day_of_week=day,
                    time_start=time(9, 0),
                    time_end=time(18, 0),
                )
            )
        db.commit()
    finally:
        db.close()


def main() -> None:
    if os.environ.get("E2E_SERVER") == "1":
        _run_migrations()
        _seed_e2e_db()
    else:
        _run_migrations()
        _ensure_single_master()

    app = asyncio.run(create_app())
    port = int(os.environ.get("PORT", "8000"))
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
