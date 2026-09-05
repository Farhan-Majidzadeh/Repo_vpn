from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    sales_mode: Literal["disabled", "private_beta", "public"] = "disabled"
    private_beta_telegram_ids: str = ""
    database_url: str = "postgresql+asyncpg://vpn:vpn@db:5432/vpn"
    redis_url: str = "redis://redis:6379/0"
    api_base_url: str = "http://api:8000"
    telegram_bot_token: str = ""
    payment_provider: str = ""
    payment_merchant_id: str = ""
    payment_callback_base_url: str = ""
    marzban_primary_base_url: str = ""
    marzban_primary_username: str = ""
    marzban_primary_password: str = ""

    @property
    def private_beta_ids(self) -> frozenset[int]:
        return frozenset(
            int(item.strip())
            for item in self.private_beta_telegram_ids.split(",")
            if item.strip()
        )

    @model_validator(mode="after")
    def protect_live_sales(self) -> "Settings":
        if self.sales_mode != "disabled" and not self.payment_provider:
            raise ValueError("PAYMENT_PROVIDER is required before enabling sales")
        if self.sales_mode != "disabled" and not self.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required before enabling sales")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
