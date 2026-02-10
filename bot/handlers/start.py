from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, WebAppInfo

from bot.api.deps import is_master_telegram_id
from bot.config.settings import settings

router = Router(name="start")


def _base_url() -> str:
    return f"https://{settings.webhook_domain.rstrip('/')}"


def _miniapp_keyboard(telegram_id: int | None) -> ReplyKeyboardMarkup:
    """Клавиатура: «Открыть запись» для всех; «Панель мастера» только для MASTER_TELEGRAM_IDS (админ без мастера не видит)."""
    url = _base_url()
    rows = [
        [
            KeyboardButton(
                text="Открыть запись",
                web_app=WebAppInfo(url=url),
            )
        ]
    ]
    if telegram_id is not None and is_master_telegram_id(telegram_id):
        rows.append(
            [
                KeyboardButton(
                    text="Панель мастера",
                    web_app=WebAppInfo(url=f"{url}?view=master"),
                )
            ]
        )
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Обработчик /start: приветствие и кнопка записи; у мастера дополнительно «Панель мастера»."""
    user_id = message.from_user.id if message.from_user else None
    await message.answer(
        "Здравствуйте! Нажмите кнопку ниже, чтобы открыть запись к мастеру.",
        reply_markup=_miniapp_keyboard(user_id),
    )
