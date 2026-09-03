"""Application configuration.

Required settings fail fast with a single clear message naming the variable
(PRS §15). No secrets are ever logged or echoed.

The session secret is resolved in this order so a fresh container needs no
configuration: an explicit ``TESQIVO_SECRET_KEY`` wins; otherwise the value is
read from ``TESQIVO_SECRET_KEY_FILE`` if that file exists; otherwise a random key
is generated and written there (0600) so it stays stable across restarts. Only
if none of that is possible does startup fail.
"""

from __future__ import annotations

import secrets
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TESQIVO_", env_file=".env", extra="ignore")

    # --- required ---
    db_url: str = Field(..., description="PostgreSQL DSN, e.g. postgresql+asyncpg://user:pw@db/tesqivo")
    redis_url: str = Field(..., description="Redis DSN, e.g. redis://redis:6379/0")
    public_url: str = Field(..., description="Absolute base URL, e.g. https://tesqivo.example.com")

    # --- session secret (auto-resolved: env > file > generated; see module docstring) ---
    secret_key: str = Field(default="", description="Session signing / CSRF secret, >= 32 bytes")
    secret_key_file: str = Field(
        default="/data/secret_key",
        description="Where an auto-generated secret is persisted when TESQIVO_SECRET_KEY is unset",
    )

    # --- first boot ---
    bootstrap_token: str | None = Field(
        default=None, description="Optional one-time gate for the browser first-admin screen"
    )

    # --- static SPA assets (set by the container image; unset => API only) ---
    static_dir: str | None = Field(
        default=None, description="Directory of the built web UI to serve at /; unset serves the API only"
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
    # Comma-separated IPs / CIDRs of reverse proxies whose forwarded-for headers
    # are trusted for the real client IP (rate limiting). "*" trusts any direct
    # peer - only safe when the app is never reachable except through your proxy.
    trusted_proxies: str = ""

    @property
    def trusted_proxy_networks(self) -> list:
        import ipaddress

        nets = []
        for part in self.trusted_proxies.split(","):
            part = part.strip()
            if not part:
                continue
            if part == "*":
                return ["*"]
            try:
                nets.append(ipaddress.ip_network(part, strict=False))
            except ValueError:
                continue
        return nets

    # --- optional outbound email (self-service password reset) ---
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_starttls: bool = True

    @field_validator("db_url")
    @classmethod
    def _async_driver(cls, v: str) -> str:
        if v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @model_validator(mode="after")
    def _resolve_secret_key(self) -> Settings:
        key = (self.secret_key or "").strip()
        if not key:
            path = Path(self.secret_key_file)
            try:
                if path.is_file():
                    key = path.read_text().strip()
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    key = secrets.token_urlsafe(48)
                    path.write_text(key)
                    path.chmod(0o600)
            except OSError:
                key = ""
        if not key:
            raise ValueError(
                "TESQIVO_SECRET_KEY is unset and no writable secret file is available "
                f"({self.secret_key_file}); set TESQIVO_SECRET_KEY to a value of at least 32 bytes"
            )
        if len(key.encode()) < 32:
            raise ValueError("TESQIVO_SECRET_KEY must be at least 32 bytes")
        self.secret_key = key
        return self

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
        names = []
        for err in exc.errors():
            loc = err.get("loc") or ()
            names.append(f"TESQIVO_{str(loc[0]).upper()}" if loc else err.get("msg", "configuration"))
        sys.stderr.write(
            f"FATAL: invalid or missing required configuration: {', '.join(names)}\n"
            "See docs/self-hosting.md for the configuration contract.\n"
        )
        raise SystemExit(78)  # EX_CONFIG
