import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from loguru import logger

from bot.config.settings import settings


async def create_app() -> web.Application:
    logger.add("logs/app.log", rotation="10 MB")

    app = web.Application()

    # Health endpoint
    async def health(request: web.Request) -> web.Response:  # noqa: ANN001
        return web.Response(text="ok")

    app.router.add_get("/health", health)

    # Telegram webhook
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()

    # TODO: register routers and handlers on dispatcher here.

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
