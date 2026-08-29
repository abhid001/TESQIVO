"""Project discovery + access requests."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentActor, DbSession, RequestCtx
from app.domain import access

router = APIRouter(tags=["access"])


class DiscoverableProjectOut(BaseModel):
    id: str
    key: str
    name: str
    description: str | None
    is_member: bool
    pending_request_role: str | None


class AccessRequestIn(BaseModel):
    requested_role: str = "tester"
    message: str | None = Field(default=None, max_length=2000)


class DecisionIn(BaseModel):
    approve: bool
    role: str | None = None


class AccessRequestOut(BaseModel):
    id: str
    project_id: str
    project_key: str
    project_name: str
    user_id: str
    username: str
    user_email: str
    user_display_name: str
    requested_role: str
    message: str | None
    status: str
    created_at: str
    decided_at: str | None


@router.get("/projects/discoverable", response_model=list[DiscoverableProjectOut])
async def list_discoverable(actor: CurrentActor, db: DbSession) -> list[DiscoverableProjectOut]:
    return [
        DiscoverableProjectOut(
            id=str(p.id),
            key=p.key,
            name=p.name,
            description=p.description,
            is_member=is_member,
            pending_request_role=pending,
        )
        for (p, is_member, pending) in await access.list_discoverable(db, actor)
    ]


@router.post("/projects/{project_id}/access-requests", status_code=201)
async def request_access(
    project_id: str,
    body: AccessRequestIn,
    actor: CurrentActor,
    db: DbSession,
    ctx: RequestCtx,
) -> dict:
    req = await access.request_access(
        db,
        actor,
        ctx,
        project_id=uuid.UUID(project_id),
        requested_role=body.requested_role,
        message=body.message,
    )
    return {"id": str(req.id), "status": req.status}


def _req_out(r, u, p) -> AccessRequestOut:
    return AccessRequestOut(
        id=str(r.id),
        project_id=str(r.project_id),
        project_key=p.key,
        project_name=p.name,
        user_id=str(r.user_id),
        username=u.username,
        user_email=u.email,
        user_display_name=u.display_name,
        requested_role=r.requested_role,
        message=r.message,
        status=r.status,
        created_at=r.created_at.isoformat(),
        decided_at=r.decided_at.isoformat() if r.decided_at else None,
    )


@router.get("/projects/{project_id}/access-requests", response_model=list[AccessRequestOut])
async def list_project_requests(
    project_id: str, actor: CurrentActor, db: DbSession, status: str = "pending"
) -> list[AccessRequestOut]:
    rows = await access.list_requests(
        db, actor, project_id=uuid.UUID(project_id), status=status
    )
    return [_req_out(r, u, p) for (r, u, p) in rows]


@router.get("/access-requests", response_model=list[AccessRequestOut])
async def list_all_requests(
    actor: CurrentActor, db: DbSession, status: str = "pending"
) -> list[AccessRequestOut]:
    rows = await access.list_requests(db, actor, status=status)
    return [_req_out(r, u, p) for (r, u, p) in rows]


@router.post("/access-requests/{request_id}/decide", response_model=AccessRequestOut)
async def decide(
    request_id: str,
    body: DecisionIn,
    actor: CurrentActor,
    db: DbSession,
    ctx: RequestCtx,
) -> AccessRequestOut:
    req = await access.decide_request(
        db, actor, ctx, request_id=uuid.UUID(request_id), approve=body.approve, role=body.role
    )
    from app.models import Project, User

    u = await db.get(User, req.user_id)
    p = await db.get(Project, req.project_id)
    return _req_out(req, u, p)
