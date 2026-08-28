"""Application configuration.

Required settings fail fast with a single clear message naming the variable
(PRS §15). No secrets are ever logged or echoed.
"""

from __future__ import annotations

import sys
from functools import lru_cache

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TESQIVO_", env_file=".env", extra="ignore")

    # --- required ---
    db_url: str = Field(..., description="PostgreSQL DSN, e.g. postgresql+asyncpg://user:pw@db/tesqivo")
    redis_url: str = Field(..., description="Redis DSN, e.g. redis://redis:6379/0")
    secret_key: str = Field(..., description="Session signing / CSRF secret, >= 32 bytes")
    public_url: str = Field(..., description="Absolute base URL, e.g. https://tesqivo.example.com")

    # --- first boot ---
    bootstrap_token: str | None = Field(
        default=None, description="One-time first-admin setup gate; required on first boot"
    )

    # --- tunables with defaults ---
    attachment_dir: str = "/data/attachments"
    max_upload_mb: int = 25
    session_ttl_hours: int = 12
    failed_login_threshold: int = 5
    failed_login_lockout_minutes: int = 15
    argon2_time_cost: int = 3
    argon2_memory_cost_kib: int = 65536
    argon2_parallelism: int = 2
    rate_limit_per_minute: int = 240
    export_sync_row_limit: int = 5000
    environment: str = "production"

    # --- optional outbound email (self-service password reset) ---
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_starttls: bool = True

    @field_validator("secret_key")
    @classmethod
    def _secret_len(cls, v: str) -> str:
        if len(v.encode()) < 32:
            raise ValueError("must be at least 32 bytes")
        return v

    @field_validator("db_url")
    @classmethod
    def _async_driver(cls, v: str) -> str:
        if v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @property
    def is_test(self) -> bool:
        return self.environment == "test"

    @property
    def email_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        missing = ", ".join(f"TESQIVO_{e['loc'][0].upper()}" for e in exc.errors())
        sys.stderr.write(
            f"FATAL: invalid or missing required configuration: {missing}\n"
            "See docs/architecture/09_deployment.md for the configuration contract.\n"
        )
        raise SystemExit(78)  # EX_CONFIG
