"""Audit service. Append-only; written in the same transaction as the mutation.

Never logs passwords, tokens, secrets, or file contents (PRS §12).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import Actor, Ctx
from app.models import AuditEvent, User

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


# --------------------------------------------------------------------------- feed

_VERB = {
    "created": "created",
    "updated": "updated",
    "submitted": "submitted for review",
    "approved": "approved",
    "active": "activated",
    "activated": "activated",
    "completed": "completed",
    "archived": "archived",
    "released": "released",
    "started": "started",
    "aborted": "aborted",
    "corrected": "corrected",
    "rejected": "rejected",
    "reopened": "reopened",
    "removed": "removed",
    "closed": "closed",
    "fulfilled": "fulfilled",
    "planned": "moved to planned",
    "in_progress": "moved to in progress",
    "in_review": "moved to review",
    "triaged": "triaged",
    "moved": "moved",
    "role_changed": "role changed",
    "added": "added",
    "scope_added": "added to scope",
    "scope_removed": "removed from scope",
    "version_refreshed": "version refreshed",
    "retest_requested": "flagged for retest",
    "defect_linked": "linked to a defect",
    "scenario_changed": "reassigned to a scenario",
    "login": "signed in",
}
_NOUN = {
    "requirement": "Requirement",
    "release": "Release",
    "defect": "Defect",
    "test_case": "Test case",
    "scenario": "Scenario",
    "plan": "Test plan",
    "cycle": "Cycle",
    "cycle_test": "Cycle test",
    "attempt": "Execution",
    "trace_link": "Trace link",
    "link": "Trace link",
    "project_membership": "Membership",
    "feedback": "Feedback",
    "folder": "Folder",
    "reference_value": "Reference value",
    "project_access_request": "Access request",
    "project": "Project",
    "session": "Session",
    "user": "User",
}
_GOOD = {"approved", "completed", "closed", "released", "active", "activated", "fulfilled"}
_BAD = {"rejected", "aborted", "reopened", "removed", "archived"}


def _summarise(ev: AuditEvent, actor_name: str) -> dict:
    tail = ev.action.split(".")[-1]
    verb = _VERB.get(tail, tail.replace("_", " "))
    noun = _NOUN.get(ev.entity_type, ev.entity_type.replace("_", " ").capitalize())
    subject = f"{noun} {ev.entity_key}".strip() if ev.entity_key else noun
    kind = "ok" if tail in _GOOD else "bad" if tail in _BAD else "info"
    return {
        "id": str(ev.id),
        "action": ev.action,
        "text": f"{subject} {verb}",
        "actor": actor_name,
        "kind": kind,
        "at": ev.occurred_at.isoformat(),
    }


async def entity_history(
    session: AsyncSession, actor: Actor, *, entity_id: uuid.UUID, project_id: uuid.UUID
) -> list[dict]:
    """Audit trail for one entity, newest first (PRS §12 — history is visible)."""
    from app.domain import authz

    authz.authorize(actor, "report.view", project_id=project_id)
    rows = (
        await session.execute(
            select(AuditEvent, User)
            .outerjoin(User, User.id == AuditEvent.actor_id)
            .where(AuditEvent.entity_id == entity_id)
            .order_by(AuditEvent.occurred_at.desc())
        )
    ).all()
    return [_summarise(ev, u.display_name if u else "System") for (ev, u) in rows]


async def recent_activity(
    session: AsyncSession, actor: Actor, *, project_id: uuid.UUID, limit: int = 15
) -> list[dict]:
    from app.domain import authz

    authz.authorize(actor, "report.view", project_id=project_id)
    rows = (
        await session.execute(
            select(AuditEvent, User)
            .outerjoin(User, User.id == AuditEvent.actor_id)
            .where(AuditEvent.project_id == project_id)
            .order_by(AuditEvent.occurred_at.desc())
            .limit(max(1, min(limit, 50)))
        )
    ).all()
    return [_summarise(ev, u.display_name if u else "System") for (ev, u) in rows]


async def project_log(
    session: AsyncSession,
    actor: Actor,
    *,
    project_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    entity_type: str | None = None,
    actor_id: uuid.UUID | None = None,
    q: str | None = None,
) -> tuple[list[dict], int]:
    """Full project activity log - every user action, not just a friendly
    recent-activity feed. Restricted to project_admin/test_manager (PRS §12:
    admins can audit who did what)."""
    from app.domain import authz

    authz.authorize(actor, "audit.view", project_id=project_id)
    stmt = select(AuditEvent, User).outerjoin(User, User.id == AuditEvent.actor_id).where(
        AuditEvent.project_id == project_id
    )
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if actor_id:
        stmt = stmt.where(AuditEvent.actor_id == actor_id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            func.lower(AuditEvent.action).like(like) | func.lower(AuditEvent.entity_key).like(like)
        )
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(AuditEvent.occurred_at.desc()).limit(page_size).offset((page - 1) * page_size)
    rows = (await session.execute(stmt)).all()
    out = []
    for ev, u in rows:
        row = _summarise(ev, u.display_name if u else "System")
        row.update({
            "actor_username": u.username if u else None,
            "entity_type": ev.entity_type,
            "entity_key": ev.entity_key,
            "action": ev.action,
            "source": ev.source,
        })
        out.append(row)
    return out, int(total)
