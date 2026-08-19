"""Application configuration, loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: str = "development"
    app_name: str = "deals-rummy"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60
    api_v1_prefix: str = "/api/v1"

    # database
    database_url: str = "postgresql+psycopg://rummy:rummy@localhost:5432/rummy"

    # redis
    redis_url: str = "redis://localhost:6379/0"

    # razorpay / real money
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    real_money_enabled: bool = True

    # game defaults
    game_min_players: int = 2
    game_max_players: int = 4
    game_default_deals: int = 2
    game_turn_seconds: int = 30
    game_starting_chips: int = 160

    frontend_origin: str = "http://localhost:5173"

    # ---- OTP (mobile register / login / password reset) ----
    # No SMS gateway wired up yet: in dev mode the OTP is generated and returned
    # directly in the API response instead of being sent by SMS. Flip to False once
    # sms_provider actually sends something.
    otp_dev_mode: bool = True
    otp_expire_minutes: int = 5

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in ("production", "prod")

    @property
    def sqlalchemy_database_url(self) -> str:
        """`database_url`, forced onto the psycopg (v3) dialect.

        Hosted Postgres providers (Render, etc.) hand out a plain
        postgres(ql):// connection string, which SQLAlchemy defaults to the
        psycopg2 dialect — not installed here, only psycopg v3 is (see
        requirements.txt). Rewrite the scheme explicitly so any DATABASE_URL,
        from any host, loads the driver we actually have.
        """
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
