"""Audit service. Append-only; written in the same transaction as the mutation.

Never logs passwords, tokens, secrets, or file contents (PRS §12).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import Actor, Ctx
from app.models import AuditEvent

_REDACT_KEYS = {
    "password",
    "password_hash",
    "current_password",
    "new_password",
    "token",
    "token_hash",
    "csrf_token",
    "secret",
    "bootstrap_token",
}


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: ("***" if k.lower() in _REDACT_KEYS else _scrub(v)) for k, v in value.items()
        }
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def record(
    session: AsyncSession,
    *,
    actor: Actor,
    ctx: Ctx,
    entity_type: str,
    action: str,
    entity_id: uuid.UUID | None = None,
    entity_key: str | None = None,
    project_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    job_id: uuid.UUID | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_type="system" if actor.username == "system" else "user",
        actor_id=None if actor.username == "system" else actor.id,
        project_id=project_id,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_key=entity_key,
        action=action,
        before=_scrub(before) if before is not None else None,
        after=_scrub(after) if after is not None else None,
        source=ctx.source.value,
        correlation_id=ctx.correlation_id,
        job_id=job_id,
    )
    session.add(event)
    return event
