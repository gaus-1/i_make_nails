import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from loguru import logger

from bot.api.miniapp.routes import setup_routes as setup_miniapp_routes
from bot.config.settings import settings
from bot.handlers import start_router


async def on_startup(bot: Bot) -> None:
    """Установка webhook при старте приложения."""
    webhook_url = f"https://{settings.webhook_domain.rstrip('/')}/webhook"
    await bot.set_webhook(webhook_url, drop_pending_updates=True)
    logger.info("Webhook set: {}", webhook_url)


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

    return app


def main() -> None:
    app = asyncio.run(create_app())
    port = int(os.environ.get("PORT", "8000"))
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
