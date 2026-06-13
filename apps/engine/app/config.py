"""Engine configuration. All secrets come from env — never hardcode."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    engine_host: str = "0.0.0.0"
    engine_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # Supabase (server-side)
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""

    # Token encryption (Fernet key)
    token_encryption_key: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Broker: Upstox
    upstox_api_key: str = ""
    upstox_api_secret: str = ""
    upstox_redirect_uri: str = "http://localhost:3000/auth/broker/callback"
    upstox_analytics_token: str = ""

    # Quant
    risk_free_rate: float = 0.065

    # AI gateway
    ai_chat_provider: str = "gemini"
    ai_chat_model: str = "gemini-3-flash"
    gemini_api_key: str = ""
    ai_alert_provider: str = "groq"
    ai_alert_model: str = "llama-3.1-8b-instant"
    groq_api_key: str = ""

    # Notifications / billing
    telegram_bot_token: str = ""
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
