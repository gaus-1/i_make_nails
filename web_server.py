import asyncio
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from loguru import logger

from bot.api.miniapp.routes import setup_routes as setup_miniapp_routes
from bot.config.settings import settings
from bot.handlers import start_router


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


async def on_startup(bot: Bot) -> None:
    """Установка webhook при старте приложения."""
    host = _normalize_webhook_domain(settings.webhook_domain)
    if not host:
        msg = "WEBHOOK_DOMAIN пустой или неверный"
        raise ValueError(msg)
    webhook_url = f"https://{host}/webhook"
    logger.info("Setting webhook: {}", webhook_url)
    await bot.set_webhook(webhook_url, drop_pending_updates=True)
    logger.info("Webhook set successfully")


async def create_app() -> web.Application:
    logger.add("logs/app.log", rotation="10 MB")

    app = web.Application()

    # Health endpoint
    async def health(request: web.Request) -> web.Response:  # noqa: ANN001
        return web.Response(text="ok")

    app.router.add_get("/health", health)

    # Mini-app HTTP API routes
    setup_miniapp_routes(app)

    # Telegram bot and webhook
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(start_router)
    dp.startup.register(on_startup)

    webhook_path = "/webhook"
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=webhook_path)
    setup_application(app, dp, bot=bot)

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


def main() -> None:
    app = asyncio.run(create_app())
    port = int(os.environ.get("PORT", "8000"))
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
