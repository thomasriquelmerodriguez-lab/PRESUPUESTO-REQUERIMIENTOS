from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Sistema de Requerimientos Presupuestarios"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    app_origin: str = "http://localhost:8000"
    database_url: str = f"sqlite+pysqlite:///{BASE_DIR / 'data' / 'app.db'}"
    secret_key: str = Field(default="development-only-change-me", min_length=16)
    initial_password: str = "2026"
    session_idle_minutes: int = 30
    session_absolute_hours: int = 8
    session_touch_seconds: int = 60
    login_attempts: int = 5
    login_window_minutes: int = 15
    upload_max_bytes: int = 10 * 1024 * 1024
    import_max_rows: int = 100_000
    import_max_columns: int = 100
    xlsx_max_uncompressed_bytes: int = 120 * 1024 * 1024
    trusted_proxy_count: int = 0
    auto_create_schema: bool = True
    seed_on_startup: bool = True
    secure_cookies: bool = False
    log_level: str = "INFO"

    @field_validator("app_origin")
    @classmethod
    def normalize_origin(cls, value: str) -> str:
        return value.rstrip("/")


    @model_validator(mode="after")
    def validate_production_security(self):
        if self.environment == "production":
            if self.secret_key == "development-only-change-me" or len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY debe ser aleatoria y tener al menos 32 caracteres en producción.")
            if not self.secure_cookies:
                raise ValueError("SECURE_COOKIES debe estar habilitado en producción.")
            if not self.app_origin.startswith("https://"):
                raise ValueError("APP_ORIGIN debe utilizar HTTPS en producción.")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def session_cookie_name(self) -> str:
        return "__Host-rq_session" if self.secure_cookies else "rq_session"


@lru_cache

def get_settings() -> Settings:
    return Settings()
