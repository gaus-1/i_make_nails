from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, WebAppInfo

from bot.config.settings import settings

router = Router(name="start")


def _miniapp_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой «Открыть мини-приложение»."""
    url = f"https://{settings.webhook_domain.rstrip('/')}"
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="Открыть запись",
                    web_app=WebAppInfo(url=url),
                )
            ]
        ],
        resize_keyboard=True,
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Обработчик /start: приветствие и кнопка открытия мини-приложения."""
    await message.answer(
        "Здравствуйте! Нажмите кнопку ниже, чтобы открыть запись к мастеру.",
        reply_markup=_miniapp_keyboard(),
    )
