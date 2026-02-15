"""Unit-тесты зависимостей API: роли, разбор списков id."""

from __future__ import annotations

import pytest

from bot.api.deps import is_master_telegram_id, resolve_telegram_role


def test_resolve_telegram_role_admin_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("bot.api.deps.settings.master_telegram_ids", "1,2")
    monkeypatch.setattr("bot.api.deps.settings.admin_telegram_ids", "1,3")
    assert resolve_telegram_role(1) == "ADMIN"
    assert resolve_telegram_role(2) == "MASTER"
    assert resolve_telegram_role(3) == "ADMIN"
    assert resolve_telegram_role(999) is None


def test_resolve_telegram_role_parses_quoted_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("bot.api.deps.settings.master_telegram_ids", '"111", 222')
    monkeypatch.setattr("bot.api.deps.settings.admin_telegram_ids", "")
    assert resolve_telegram_role(111) == "MASTER"
    assert resolve_telegram_role(222) == "MASTER"


def test_is_master_telegram_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("bot.api.deps.settings.master_telegram_ids", "111, 222")
    assert is_master_telegram_id(111) is True
    assert is_master_telegram_id(222) is True
    assert is_master_telegram_id(333) is False
