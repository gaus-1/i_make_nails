"""Unit-тесты проверки initData Telegram Web App."""

from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlencode

from bot.api.telegram_auth import get_user_id_from_validated, validate_init_data


def _make_valid_init_data(bot_token: str, user_id: int = 111, auth_date: int | None = None) -> str:
    """Собирает init_data с корректной HMAC-подписью для тестов."""
    if auth_date is None:
        auth_date = int(time.time())
    user_str = '{"id":' + str(user_id) + "}"
    data_dict = {"auth_date": str(auth_date), "user": user_str}
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
    data_dict["hash"] = computed_hash
    return urlencode(data_dict)


def test_validate_init_data_returns_none_for_empty_string() -> None:
    assert validate_init_data("", "token") is None
    assert validate_init_data("   ", "token") is None


def test_validate_init_data_returns_none_for_empty_token() -> None:
    raw = _make_valid_init_data("t")
    assert validate_init_data(raw, "") is None


def test_validate_init_data_returns_none_when_hash_missing() -> None:
    # данные без hash
    payload = "auth_date=1234567890&user=%7B%22id%22%3A111%7D"
    assert validate_init_data(payload, "token") is None


def test_validate_init_data_returns_none_for_wrong_hash() -> None:
    raw = _make_valid_init_data("token")
    raw_bad = raw.replace("hash=", "hash=deadbeef", 1)
    assert validate_init_data(raw_bad, "token") is None


def test_validate_init_data_returns_none_when_auth_date_missing() -> None:
    # валидный hash но без auth_date в данных (подпись будет от других полей)
    data_dict = {"user": '{"id":111}'}
    sorted_items = sorted(data_dict.items())
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted_items)
    secret_key = hmac.new(b"WebAppData", b"token", hashlib.sha256).digest()
    h = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    data_dict["hash"] = h
    raw = urlencode(data_dict)
    assert validate_init_data(raw, "token") is None


def test_validate_init_data_returns_none_when_auth_date_expired() -> None:
    auth_date = int(time.time()) - 100000  # давно
    raw = _make_valid_init_data("token", auth_date=auth_date)
    assert validate_init_data(raw, "token", ttl_seconds=1000) is None


def test_validate_init_data_returns_data_dict_when_valid() -> None:
    raw = _make_valid_init_data("test_bot_token", user_id=555)
    result = validate_init_data(raw, "test_bot_token")
    assert result is not None
    assert result.get("user") == '{"id":555}'
    assert "auth_date" in result
    assert "hash" not in result  # pop'нули


def test_get_user_id_from_validated() -> None:
    assert get_user_id_from_validated({"user": '{"id":123}'}) == 123
    assert get_user_id_from_validated({"user": '{"id": 456}'}) == 456
    assert get_user_id_from_validated({}) is None
    assert get_user_id_from_validated({"user": ""}) is None
    assert get_user_id_from_validated({"user": "not-json"}) is None
    assert get_user_id_from_validated({"user": "{}"}) is None
