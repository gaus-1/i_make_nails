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


# Параметр в URL Mini App, чтобы обойти кэш Telegram (при проблемах с кэшем — увеличить).
_MINIAPP_CACHE_BUST = "v=3"


def _miniapp_url(view_master: bool = False) -> str:
    """URL для открытия Mini App с cache-bust, чтобы клиент запросил свежую версию."""
    base = _base_url()
    params = [_MINIAPP_CACHE_BUST]
    if view_master:
        params.append("view=master")
    return f"{base}?{'&'.join(params)}"


def _miniapp_keyboard(telegram_id: int | None) -> InlineKeyboardMarkup:
    """Inline-кнопки Web App: с них Telegram передаёт initData (reply keyboard — нет)."""
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="Открыть запись",
                web_app=WebAppInfo(url=_miniapp_url(view_master=False)),
            )
        ]
    ]
    if telegram_id is not None and is_master_telegram_id(telegram_id):
        rows.append(
            [
                InlineKeyboardButton(
                    text="Панель мастера",
                    web_app=WebAppInfo(url=_miniapp_url(view_master=True)),
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


# Ширина inline-клавиатуры в Telegram привязана к ширине текста сообщения.
# Короткий текст — узкий пузырь и узкие кнопки. Паддинг до ~29 символов растягивает клавиатуру.
_START_TEXT_PAD_TO = 29
_ZERO_WIDTH_JOINER_HTML = "&#x200D;"


def _start_message_text() -> str:
    """Текст «Нажмите:» по центру широкого пузыря; паддинг растягивает клавиатуру на всю ширину."""
    base = "Нажмите:"
    pad_total = max(0, _START_TEXT_PAD_TO - len(base))
    pad_left = pad_total // 2
    pad_right = pad_total - pad_left
    return " " * pad_left + base + " " * pad_right + _ZERO_WIDTH_JOINER_HTML


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Обработчик /start: приветствие и кнопка записи; у мастера дополнительно «Панель мастера»."""
    user_id = message.from_user.id if message.from_user else None
    await message.answer(
        _start_message_text(),
        reply_markup=_miniapp_keyboard(user_id),
        parse_mode="HTML",
    )
