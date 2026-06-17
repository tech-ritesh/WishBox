"""Application settings, loaded from environment / .env.

Unlike the reference project (which shipped a hardcoded secret), WishBox refuses
to start in production with an insecure SECRET_KEY.
"""
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
INSECURE_DEFAULT = "change-me-to-a-long-random-string"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_prefix="WISHBOX_",
        case_sensitive=False,
        extra="ignore",
    )

    SECRET_KEY: str = INSECURE_DEFAULT
    ENV: str = "development"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_MINUTES: int = 30
    REFRESH_TOKEN_DAYS: int = 14

    DATABASE_URL: str = f"sqlite:///{(BACKEND_ROOT / 'wishbox.db').as_posix()}"
    STATIC_DIR: str = str(BACKEND_ROOT / "static")
    UPLOAD_DIR: str = str(BACKEND_ROOT / "static" / "uploads")
    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024  # 5 MB
    ALLOWED_UPLOAD_TYPES: List[str] = ["image/jpeg", "image/png", "image/webp", "image/gif"]

    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    LLM_API_KEY: str = ""

    # --- Payments (Razorpay). Blank keys => local MOCK gateway (offline-friendly). ---
    PAYMENT_PROVIDER: str = "mock"          # mock | razorpay
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

    # --- Tax / GST ---
    GST_PERCENT: float = 18.0               # default GST applied to taxable subtotal
    GST_INCLUSIVE: bool = True              # True = listed prices already include GST (Indian retail norm)
    STORE_GSTIN: str = "27AAAAA0000A1Z5"    # seller GSTIN printed on invoices (demo value)

    # --- Email (SMTP optional; blank => console + outbox only) ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "WishBox <no-reply@wishbox.local>"

    # --- SMS (Twilio optional; blank => console + outbox only) ---
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""

    # --- Background worker ---
    ENABLE_WORKER: bool = True              # in-process scheduler for reminders/outbox
    WORKER_INTERVAL_SECONDS: int = 60

    # Public base URL used to build links in emails (verification, reset, tracking)
    APP_BASE_URL: str = "http://localhost:5173"

    @property
    def razorpay_enabled(self) -> bool:
        return (
            self.PAYMENT_PROVIDER.lower() == "razorpay"
            and bool(self.RAZORPAY_KEY_ID)
            and bool(self.RAZORPAY_KEY_SECRET)
        )

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @field_validator("SECRET_KEY")
    @classmethod
    def _validate_secret(cls, v: str) -> str:
        return v


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_production and s.SECRET_KEY == INSECURE_DEFAULT:
        raise RuntimeError(
            "Refusing to start in production with the default SECRET_KEY. "
            "Set WISHBOX_SECRET_KEY in the environment."
        )
    return s


settings = get_settings()
