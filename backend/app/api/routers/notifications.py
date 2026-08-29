"""Per-user notification inbox: list, mark read, mark all read."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentActor, DbSession
from app.domain import notifications
from app.models import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    id: str
    kind: str
    title: str
    body: str | None
    link: str | None
    created_at: str
    read: bool


def _out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=str(n.id),
        kind=n.kind,
        title=n.title,
        body=n.body,
        link=n.link,
        created_at=n.created_at.isoformat(),
        read=n.read_at is not None,
    )


@router.get("")
async def list_notifications(
    actor: CurrentActor, db: DbSession, unread_only: bool = False, limit: int = 40
) -> dict:
    rows = await notifications.list_for(db, actor, unread_only=unread_only, limit=limit)
    return {"items": [_out(n) for n in rows], "unread": await notifications.unread_count(db, actor)}


@router.post("/{notification_id}/read", status_code=204)
async def mark_read(notification_id: str, actor: CurrentActor, db: DbSession):
    await notifications.mark_read(db, actor, notification_id=uuid.UUID(notification_id))


@router.post("/read-all", status_code=204)
async def mark_all_read(actor: CurrentActor, db: DbSession):
    await notifications.mark_all_read(db, actor)
