"""Product feedback: any signed-in user can submit; a system administrator triages
and exports. Feedback is instance-wide (optionally tagged with the project the user
was in) and is never visible to other non-admin users.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import Actor, Ctx
from app.core.errors import Forbidden, ResourceNotFound, ValidationFailed
from app.domain import audit
from app.models import Feedback, Project, User

CATEGORIES = ("bug", "idea", "question", "other")
STATUSES = ("open", "reviewing", "resolved")
_MAX_LEN = 5000


def _now() -> datetime:
    return datetime.now(UTC)


def _require_admin(actor: Actor) -> None:
    if not actor.is_system_admin:
        raise Forbidden("System administrator access required.")


async def submit_feedback(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    message: str,
    category: str = "other",
    project_id: uuid.UUID | None = None,
    page_path: str | None = None,
) -> Feedback:
    message = (message or "").strip()
    if not message:
        raise ValidationFailed("Feedback message must not be empty.")
    if len(message) > _MAX_LEN:
        raise ValidationFailed(f"Feedback message is too long ({_MAX_LEN} characters max).")
    if category not in CATEGORIES:
        category = "other"
    if project_id is not None and await session.get(Project, project_id) is None:
        project_id = None
    page = (page_path or "").strip()[:400] or None
    fb = Feedback(
        user_id=actor.id,
        project_id=project_id,
        category=category,
        message=message,
        page_path=page,
        status="open",
    )
    session.add(fb)
    await session.flush()
    audit.record(
        session,
        actor=actor,
        ctx=ctx,
        entity_type="feedback",
        action="feedback.submitted",
        entity_id=fb.id,
        project_id=project_id,
        after={"category": category},
    )
    from app.domain import notifications

    notifications.queue(
        session,
        user_ids=await notifications.system_admin_ids(session),
        kind="feedback",
        title=f"{category.capitalize()} feedback from {actor.username}",
        body=message,
        link="/admin/feedback",
        ref_id=fb.id,
    )
    await session.commit()
    return fb


async def list_feedback(
    session: AsyncSession, actor: Actor, *, status: str | None = None
) -> list[tuple[Feedback, User, Project | None]]:
    _require_admin(actor)
    stmt = (
        select(Feedback, User, Project)
        .join(User, User.id == Feedback.user_id)
        .outerjoin(Project, Project.id == Feedback.project_id)
        .order_by(Feedback.created_at.desc())
    )
    if status in STATUSES:
        stmt = stmt.where(Feedback.status == status)
    return list((await session.execute(stmt)).all())


async def update_feedback(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    feedback_id: uuid.UUID,
    status: str | None = None,
    admin_note: str | None = None,
) -> Feedback:
    _require_admin(actor)
    fb = await session.get(Feedback, feedback_id)
    if fb is None:
        raise ResourceNotFound("Feedback not found.")
    if status is not None:
        if status not in STATUSES:
            raise ValidationFailed("status must be one of: " + ", ".join(STATUSES))
        fb.status = status
        if status == "resolved":
            fb.resolved_by = actor.id
            fb.resolved_at = _now()
        else:
            fb.resolved_by = None
            fb.resolved_at = None
    if admin_note is not None:
        fb.admin_note = admin_note.strip() or None
    audit.record(
        session,
        actor=actor,
        ctx=ctx,
        entity_type="feedback",
        action="feedback.triaged",
        entity_id=fb.id,
        after={"status": fb.status},
    )
    await session.commit()
    return fb


def feedback_csv(rows: list[tuple[Feedback, User, Project | None]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        ["submitted_at", "category", "status", "user", "email", "project", "page", "message", "admin_note"]
    )
    for fb, user, project in rows:
        w.writerow(
            [
                fb.created_at.isoformat(),
                fb.category,
                fb.status,
                user.username if user else "",
                user.email if user else "",
                project.key if project else "",
                fb.page_path or "",
                fb.message,
                fb.admin_note or "",
            ]
        )
    return buf.getvalue()


def feedback_text(rows: list[tuple[Feedback, User, Project | None]]) -> str:
    blocks: list[str] = []
    for fb, user, project in rows:
        who = f"{user.username} <{user.email}>" if user else "unknown"
        head = f"[{fb.created_at.isoformat()}]  {fb.category.upper()}  ({fb.status})"
        if project:
            head += f"  project={project.key}"
        note = f"\nAdmin note: {fb.admin_note}" if fb.admin_note else ""
        blocks.append(
            f"{head}\nFrom: {who}\nPage: {fb.page_path or '-'}\n\n{fb.message}{note}\n"
            + "-" * 72
        )
    return ("\n".join(blocks) + "\n") if blocks else "No feedback.\n"
