"""Фасад маршрутов мини-аппа: регистрирует client и master routes."""

from aiohttp import web

from bot.api.miniapp import client_routes, master_routes


def setup_routes(app: web.Application) -> None:
    """Attach mini-app routes to aiohttp application."""
    app.add_routes(client_routes.routes)
    app.add_routes(master_routes.routes)
