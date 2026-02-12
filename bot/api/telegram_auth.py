"""Проверка initData Telegram Web App на бэкенде (HMAC-SHA256)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from loguru import logger


def validate_init_data(init_data_raw: str, bot_token: str, ttl_seconds: int = 86400) -> dict | None:
    """Проверяет подпись initData и возвращает распарсенные данные или None.

    По документации Telegram: secret_key = HMAC_SHA256("WebAppData", bot_token);
    data_check_string — все пары кроме hash, сортировка по ключу, разделитель \\n.
    """
    if not init_data_raw or not bot_token:
        return None
    try:
        pairs = parse_qsl(init_data_raw, keep_blank_values=True)
        data_dict = dict(pairs)
    except Exception as exc:
        logger.debug("initData parse_qsl failed: {}", exc)
        return None

    received_hash = data_dict.pop("hash", None)
    if not received_hash:
        return None

    sorted_items = sorted(data_dict.items())
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted_items)

    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256,
    ).digest()
    computed_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        logger.warning("initData signature mismatch")
        return None

    auth_date_str = data_dict.get("auth_date")
    if not auth_date_str:
        return None
    try:
        auth_date = int(auth_date_str)
    except ValueError:
        return None
    if time.time() - auth_date > ttl_seconds:
        logger.warning("initData auth_date expired")
        return None

    return data_dict


def get_user_id_from_validated(validated: dict) -> int | None:
    """Из проверенного initData извлекает user.id."""
    user_str = validated.get("user")
    if not user_str:
        return None
    try:
        user = json.loads(user_str)
        return user.get("id")
    except (json.JSONDecodeError, TypeError):
        return None
