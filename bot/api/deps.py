from __future__ import annotations

"""Common dependencies and helpers for HTTP API handlers."""

import json
from datetime import date
from typing import NoReturn

from aiohttp import web
from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.config.settings import settings
from bot.database.engine import SessionLocal
from bot.models import Master


def get_db() -> Session:
    """Return a new database session.

    NOTE: Handlers are responsible for closing it via a context manager:

        with get_db() as db:
            ...
    """

    return SessionLocal()


def parse_date(param_name: str, raw_value: str | None) -> date:
    """Parse a YYYY-MM-DD date from query parameters with a clear error."""
    if not raw_value:
        msg = f"Missing required query parameter '{param_name}'."
        bad_request(msg, code="missing_parameter")

    try:
        return date.fromisoformat(raw_value)  # type: ignore[arg-type]
    except ValueError as exc:
        msg = f"Invalid date format for '{param_name}', expected YYYY-MM-DD."
        bad_request(msg, code="invalid_date", exc=exc)


def parse_int(param_name: str, raw_value: str | None) -> int:
    """Parse an integer from query parameters with a clear error."""
    if not raw_value:
        msg = f"Missing required query parameter '{param_name}'."
        bad_request(msg, code="missing_parameter")

    try:
        return int(raw_value)
    except ValueError as exc:  # pragma: no cover - defensive
        msg = f"Invalid integer value for '{param_name}'."
        bad_request(msg, code="invalid_integer", exc=exc)


def get_telegram_id(request: web.Request) -> int:
    """Extract Telegram user id from headers or query for v1 mini-app endpoints.

    For local debugging we support both:
    - X-Telegram-Id header
    - telegram_id query parameter
    """
    header_value = request.headers.get("X-Telegram-Id")
    query_value = request.query.get("telegram_id")

    raw_value = header_value or query_value
    if raw_value is None:
        msg = "Telegram id is required. Provide X-Telegram-Id header or telegram_id query param."
        bad_request(msg, code="missing_telegram_id")

    try:
        return int(raw_value)
    except ValueError as exc:
        msg = "Invalid Telegram id. Expected integer."
        bad_request(msg, code="invalid_telegram_id", exc=exc)


def _get_single_master_id(db: Session) -> int:
    """Return id of the single master in v1 or raise if not found."""
    master = db.execute(select(Master)).scalars().first()
    if master is None:
        msg = "Master record not found. Run onboarding first."
        bad_request(msg, code="master_not_found")
    return master.id


def bad_request(message: str, code: str = "bad_request", exc: Exception | None = None) -> NoReturn:
    """Raise HTTP 400 with a unified JSON error body."""
    raise _json_http_error(web.HTTPBadRequest, message=message, code=code) from exc


def not_found(message: str, code: str = "not_found") -> NoReturn:
    """Raise HTTP 404 with a unified JSON error body."""
    raise _json_http_error(web.HTTPNotFound, message=message, code=code)


def conflict(message: str, code: str = "conflict") -> NoReturn:
    """Raise HTTP 409 with a unified JSON error body."""
    raise _json_http_error(web.HTTPConflict, message=message, code=code)


def forbidden(message: str, code: str = "forbidden") -> NoReturn:
    """Raise HTTP 403 with a unified JSON error body."""
    raise _json_http_error(web.HTTPForbidden, message=message, code=code)


def _parse_id_list(raw: str) -> set[int]:
    """Parse comma/space-separated list of integer ids."""
    result: set[int] = set()
    for part in raw.replace(" ", "").split(","):
        if not part:
            continue
        try:
            result.add(int(part))
        except ValueError:
            # Некорректные значения игнорируем, чтобы не падать из-за env.
            continue
    return result


def resolve_telegram_role(telegram_id: int) -> str | None:
    """Return role name for telegram id: 'MASTER', 'ADMIN' or None."""
    master_ids = _parse_id_list(settings.master_telegram_ids)
    admin_ids = _parse_id_list(settings.admin_telegram_ids)

    if telegram_id in admin_ids:
        return "ADMIN"
    if telegram_id in master_ids:
        return "MASTER"
    return None


def is_master_telegram_id(telegram_id: int) -> bool:
    """True if telegram_id is in MASTER_TELEGRAM_IDS. Used in bot to show «Панель мастера» only to the master (admin-only users do not see it)."""
    master_ids = _parse_id_list(settings.master_telegram_ids)
    return telegram_id in master_ids


def require_master(db: Session, request: web.Request) -> int:
    """Ensure that current telegram user is a master/admin and return master id.

    v1: мы работаем с одним мастером, поэтому возвращаем id единственного мастера.
    В будущем здесь можно будет искать master_id по telegram_id.
    """

    telegram_id = get_telegram_id(request)
    role = resolve_telegram_role(telegram_id)
    if role not in {"MASTER", "ADMIN"}:
        forbidden("Доступ разрешён только мастеру.", code="master_required")

    return _get_single_master_id(db)


def _json_http_error(
    exc_cls: type[web.HTTPException],
    *,
    message: str,
    code: str,
) -> web.HTTPException:
    """Construct an aiohttp HTTPException with JSON body."""
    payload = {"error": message, "code": code}
    body = json.dumps(payload, ensure_ascii=False)
    return exc_cls(text=body, content_type="application/json")
