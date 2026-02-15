from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from bot.api.deps import is_master_telegram_id
from bot.config.settings import settings

router = Router(name="start")


def _base_url() -> str:
    """Базовый URL мини-аппа по WEBHOOK_DOMAIN."""
    return f"https://{settings.webhook_domain.rstrip('/')}"


def _miniapp_keyboard(telegram_id: int | None) -> InlineKeyboardMarkup:
    """Inline-кнопки Web App: с них Telegram передаёт initData (reply keyboard — нет)."""
    url = _base_url()
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="Открыть запись",
                web_app=WebAppInfo(url=url),
            )
        ]
    ]
    if telegram_id is not None and is_master_telegram_id(telegram_id):
        rows.append(
            [
                InlineKeyboardButton(
                    text="Панель мастера",
                    web_app=WebAppInfo(url=f"{url}?view=master"),
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Обработчик /start: приветствие и кнопка записи; у мастера дополнительно «Панель мастера»."""
    user_id = message.from_user.id if message.from_user else None
    await message.answer(
        "Здравствуйте! Нажмите кнопку ниже, чтобы открыть запись к мастеру.",
        reply_markup=_miniapp_keyboard(user_id),
    )
