from __future__ import annotations

"""Зависимости и хелперы для HTTP API: сессия БД, telegram_id, роли, HTTP-ошибки."""

import json
from datetime import date
from typing import NoReturn

from aiohttp import web
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.api.telegram_auth import get_user_id_from_validated, validate_init_data
from bot.config.settings import settings
from bot.database.engine import SessionLocal
from bot.models import Master


def get_db() -> Session:
    """Новая сессия БД. Использовать как with get_db() as db: ..."""
    return SessionLocal()


def parse_date(param_name: str, raw_value: str | None) -> date:
    """Парсит дату YYYY-MM-DD из query; при ошибке — понятный bad_request."""
    if not raw_value:
        msg = f"Missing required query parameter '{param_name}'."
        bad_request(msg, code="missing_parameter")

    try:
        return date.fromisoformat(raw_value)  # type: ignore[arg-type]
    except ValueError as exc:
        msg = f"Invalid date format for '{param_name}', expected YYYY-MM-DD."
        bad_request(msg, code="invalid_date", exc=exc)


def parse_int(param_name: str, raw_value: str | None) -> int:
    """Парсит целое из query; при ошибке — bad_request."""
    if not raw_value:
        msg = f"Missing required query parameter '{param_name}'."
        bad_request(msg, code="missing_parameter")

    try:
        return int(raw_value)
    except ValueError as exc:  # pragma: no cover - defensive
        msg = f"Invalid integer value for '{param_name}'."
        bad_request(msg, code="invalid_integer", exc=exc)


def get_telegram_id(request: web.Request) -> int:
    """Telegram user id из заголовка X-Telegram-Id или query telegram_id (для dev)."""
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


def get_telegram_id_from_request(request: web.Request) -> int:
    """Идентификация: initData (если валиден) или fallback на X-Telegram-Id при истечении/сбое."""
    init_data_raw = (request.headers.get("X-Telegram-Init-Data") or "").strip()
    has_header = request.headers.get("X-Telegram-Id") is not None
    has_query = request.query.get("telegram_id") is not None

    if init_data_raw and settings.miniapp_auth != "dev":
        validated = validate_init_data(
            init_data_raw,
            settings.telegram_bot_token,
            ttl_seconds=settings.init_data_ttl_seconds,
        )
        if validated is not None:
            user_id = get_user_id_from_validated(validated)
            if user_id is not None:
                return user_id
        logger.info(
            "miniapp auth: initData len={} valid=no, fallback header={} query={}",
            len(init_data_raw),
            has_header,
            has_query,
        )
    elif not init_data_raw:
        logger.info(
            "miniapp auth: initData empty, fallback header={} query={}",
            has_header,
            has_query,
        )
    return get_telegram_id(request)


def _get_single_master_id(db: Session) -> int:
    """Id единственного мастера в v1; иначе bad_request."""
    master = db.execute(select(Master)).scalars().first()
    if master is None:
        msg = "Master record not found. Run onboarding first."
        bad_request(msg, code="master_not_found")
    return master.id


def bad_request(message: str, code: str = "bad_request", exc: Exception | None = None) -> NoReturn:
    """HTTP 400 с JSON { error, code }."""
    raise _json_http_error(web.HTTPBadRequest, message=message, code=code) from exc


def not_found(message: str, code: str = "not_found") -> NoReturn:
    """HTTP 404 с JSON { error, code }."""
    raise _json_http_error(web.HTTPNotFound, message=message, code=code)


def conflict(message: str, code: str = "conflict") -> NoReturn:
    """HTTP 409 с JSON { error, code }."""
    raise _json_http_error(web.HTTPConflict, message=message, code=code)


def forbidden(message: str, code: str = "forbidden") -> NoReturn:
    """HTTP 403 с JSON { error, code }."""
    raise _json_http_error(web.HTTPForbidden, message=message, code=code)


def unauthorized(message: str, code: str = "invalid_init_data") -> NoReturn:
    """HTTP 401 с JSON { error, code }."""
    raise _json_http_error(web.HTTPUnauthorized, message=message, code=code)


def _parse_id_list(raw: str) -> frozenset[int]:
    """Парсит список целых id (запятая/пробел), убирает кавычки из значений (Railway ENV). O(1) lookup."""
    result: set[int] = set()
    for part in raw.replace(" ", "").split(","):
        part = part.strip().strip("\"'")
        if not part:
            continue
        try:
            result.add(int(part))
        except ValueError:
            continue
    return frozenset(result)


def resolve_telegram_role(telegram_id: int) -> str | None:
    """Роль по telegram_id: 'MASTER', 'ADMIN' или None."""
    master_ids = _parse_id_list(settings.master_telegram_ids)
    admin_ids = _parse_id_list(settings.admin_telegram_ids)

    if telegram_id in admin_ids:
        return "ADMIN"
    if telegram_id in master_ids:
        return "MASTER"
    return None


def is_master_telegram_id(telegram_id: int) -> bool:
    """Входит ли id в MASTER_TELEGRAM_IDS (кнопка «Панель мастера» только у мастера)."""
    master_ids = _parse_id_list(settings.master_telegram_ids)
    return telegram_id in master_ids


def is_owner_telegram_id(telegram_id: int) -> bool:
    """Входит ли id в OWNER_TELEGRAM_IDS (кнопка «Как клиент» в панели мастера)."""
    if not settings.owner_telegram_ids.strip():
        return False
    return telegram_id in _parse_id_list(settings.owner_telegram_ids)


def require_master(db: Session, request: web.Request) -> int:
    """Проверяет, что пользователь — мастер или админ, возвращает id единственного мастера."""
    telegram_id = get_telegram_id_from_request(request)
    role = resolve_telegram_role(telegram_id)
    if role not in {"MASTER", "ADMIN"}:
        logger.info(
            "miniapp master_required: telegram_id={} not in MASTER/ADMIN_IDS",
            telegram_id,
        )
        forbidden("Доступ разрешён только мастеру.", code="master_required")

    return _get_single_master_id(db)


def _json_http_error(
    exc_cls: type[web.HTTPException],
    *,
    message: str,
    code: str,
) -> web.HTTPException:
    """Собирает HTTPException с телом JSON { error, code }."""
    payload = {"error": message, "code": code}
    body = json.dumps(payload, ensure_ascii=False)
    return exc_cls(text=body, content_type="application/json")
