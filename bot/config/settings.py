from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    database_url: str = Field(..., alias="DATABASE_URL")
    secret_key: str = Field(..., alias="SECRET_KEY")

    master_telegram_ids: str = Field(..., alias="MASTER_TELEGRAM_IDS")
    admin_telegram_ids: str = Field(..., alias="ADMIN_TELEGRAM_IDS")

    timezone: str = Field("Europe/Moscow", alias="TIMEZONE")
    webhook_domain: str = Field(..., alias="WEBHOOK_DOMAIN")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

