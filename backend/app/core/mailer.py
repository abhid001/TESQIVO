"""Outbound email (optional). Phase 1 uses it only for self-service password reset.

If SMTP is not configured, `get_mailer()` returns a `NullMailer` and callers must
check `settings.email_enabled` before offering an email-based flow.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

from app.core.config import get_settings

log = logging.getLogger("tesqivo.mailer")


class Mailer(Protocol):
    async def send(self, *, to: str, subject: str, body: str) -> None: ...


class NullMailer:
    async def send(self, *, to: str, subject: str, body: str) -> None:  # noqa: ARG002
        raise RuntimeError("Email is not configured on this instance.")


class SmtpMailer:
    async def send(self, *, to: str, subject: str, body: str) -> None:
        await asyncio.to_thread(self._send_sync, to, subject, body)

    def _send_sync(self, to: str, subject: str, body: str) -> None:
        s = get_settings()
        msg = EmailMessage()
        msg["From"] = s.smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as server:
            server.ehlo()
            if s.smtp_starttls:
                server.starttls()
                server.ehlo()
            if s.smtp_user and s.smtp_password:
                server.login(s.smtp_user, s.smtp_password)
            server.send_message(msg)
        log.info("sent password-reset email", extra={"to_domain": to.split("@")[-1]})


class CapturingMailer:
    """Test double: records messages instead of sending."""

    def __init__(self) -> None:
        self.outbox: list[dict[str, str]] = []

    async def send(self, *, to: str, subject: str, body: str) -> None:
        self.outbox.append({"to": to, "subject": subject, "body": body})


_mailer: Mailer | None = None


def get_mailer() -> Mailer:
    global _mailer
    if _mailer is not None:
        return _mailer
    settings = get_settings()
    _mailer = SmtpMailer() if settings.email_enabled else NullMailer()
    return _mailer


def set_mailer_for_tests(m: Mailer | None) -> None:
    global _mailer
    _mailer = m
