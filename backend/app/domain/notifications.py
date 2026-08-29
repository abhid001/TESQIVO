"""Per-user notification inbox.

Events (new feedback, access requests) fan out a Notification row to each
recipient. `queue()` only stages the rows — the caller commits in the same
transaction as the event it describes.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import Actor
from app.core.errors import ResourceNotFound
from app.models import Notification, ProjectMembership, User


def _now() -> datetime:
    return datetime.now(UTC)


async def system_admin_ids(session: AsyncSession) -> list[uuid.UUID]:
    return list(
        (
            await session.scalars(
                select(User.id).where(
                    User.is_system_admin.is_(True), User.status == "active"
                )
            )
        ).all()
    )


async def project_admin_ids(session: AsyncSession, project_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        (
            await session.scalars(
                select(ProjectMembership.user_id).where(
                    ProjectMembership.project_id == project_id,
                    ProjectMembership.role == "project_admin",
                    ProjectMembership.status == "active",
                )
            )
        ).all()
    )


def queue(
    session: AsyncSession,
    *,
    user_ids: Iterable[uuid.UUID],
    kind: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
    ref_id: uuid.UUID | None = None,
) -> None:
    for uid in set(user_ids):
        session.add(
            Notification(
                user_id=uid,
                kind=kind,
                title=title[:200],
                body=((body or "").strip()[:500] or None),
                link=link,
                ref_id=ref_id,
            )
        )


async def list_for(
    session: AsyncSession, actor: Actor, *, unread_only: bool = False, limit: int = 40
) -> list[Notification]:
    stmt = (
        select(Notification)
        .where(Notification.user_id == actor.id)
        .order_by(Notification.created_at.desc())
        .limit(max(1, min(limit, 100)))
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    return list((await session.scalars(stmt)).all())


async def unread_count(session: AsyncSession, actor: Actor) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == actor.id, Notification.read_at.is_(None))
        )
        or 0
    )


async def mark_read(session: AsyncSession, actor: Actor, *, notification_id: uuid.UUID) -> None:
    n = await session.get(Notification, notification_id)
    if n is None or n.user_id != actor.id:
        raise ResourceNotFound("Notification not found.")
    if n.read_at is None:
        n.read_at = _now()
        await session.commit()


async def mark_all_read(session: AsyncSession, actor: Actor) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.user_id == actor.id, Notification.read_at.is_(None))
        .values(read_at=_now())
    )
    await session.commit()
