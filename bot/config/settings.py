"""Конфигурация приложения из переменных окружения."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Параметры из env: токен бота, БД, мастер/админ, мини-апп."""

    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    database_url: str = Field(..., alias="DATABASE_URL")
    secret_key: str = Field(..., alias="SECRET_KEY")

    master_telegram_ids: str = Field(..., alias="MASTER_TELEGRAM_IDS")
    admin_telegram_ids: str = Field(..., alias="ADMIN_TELEGRAM_IDS")

    timezone: str = Field("Europe/Moscow", alias="TIMEZONE")
    webhook_domain: str = Field(..., alias="WEBHOOK_DOMAIN")

    # Мини-апп: dev — принимать X-Telegram-Id без проверки initData; иначе требовать initData.
    miniapp_auth: str = Field("prod", alias="MINIAPP_AUTH")
    init_data_ttl_seconds: int = Field(86400, alias="INIT_DATA_TTL_SECONDS")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
