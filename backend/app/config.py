from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: str = "production"
    app_secret: str = "dev-only-change-me"
    database_url: str = "sqlite:///./vpn.db"
    redis_url: str = "redis://localhost:6379/0"
    public_api_url: str = "http://localhost:8000"

    telegram_bot_token: str = ""
    telegram_admin_ids: str = ""

    panel_kind: str = "mock"
    panel_base_url: str = ""
    panel_username: str = ""
    panel_password: str = ""
    panel_verify_tls: bool = True
    marzban_subscription_base_url: str = ""

    xui_inbound_id: int = 1
    xui_public_host: str = ""
    xui_public_port: int = 443

    default_currency: str = "IRR"
    healthcheck_interval_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
