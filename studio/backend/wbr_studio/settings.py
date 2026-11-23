"""运行配置。环境变量优先，studio/.env 仅在进程环境没有同名变量时补上。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.is_file() else None,
        extra="ignore",
    )

    database_url: str
    redis_url: str = "redis://127.0.0.1:6379/0"
    studio_secret_key: str = ""
    studio_fernet_key: str = ""
    studio_run_inline: bool = False
    studio_jwt_ttl_minutes: int = Field(default=60 * 24 * 7, gt=0)
    studio_refresh_ttl_days: int = Field(default=30, gt=0)
    studio_cors_origins: str = "http://localhost:5173"
    studio_run_timeout_seconds: int = Field(default=900, gt=0)
    studio_invite_ttl_hours: int = Field(default=72, gt=0)
    studio_email_token_ttl_hours: int = Field(default=24, gt=0)
    studio_auth_rate_limit: int = Field(default=20, gt=0)
    studio_auth_rate_window_seconds: int = Field(default=60, gt=0)
    studio_rate_limit_backend: str = "memory"
    studio_require_email_verification: bool = False

    @field_validator("studio_rate_limit_backend")
    @classmethod
    def _rate_backend(cls, value: str) -> str:
        text = value.strip().lower()
        if text not in {"memory", "redis"}:
            raise ValueError("STUDIO_RATE_LIMIT_BACKEND 只能是 memory 或 redis")
        return text

    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.studio_cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings() -> None:
    get_settings.cache_clear()
