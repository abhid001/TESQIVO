"""Projects, membership, reference data (increment 3)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentActor, DbSession, RequestCtx
from app.domain import authz, projects
from app.models import Project, ProjectMembership, ReferenceValue, User

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectOut(BaseModel):
    id: str
    key: str
    name: str
    description: str | None
    status: str
    timezone: str
    version: int


class CreateProjectRequest(BaseModel):
    key: str = Field(min_length=2, max_length=16)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    timezone: str = "UTC"


class NewUser(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: str
    display_name: str = ""
    password: str = Field(min_length=12, max_length=256)


class MemberRequest(BaseModel):
    role: str
    user_id: str | None = None
    new_user: NewUser | None = None


class ReferenceRequest(BaseModel):
    kind: str
    value: str


def _out(p: Project) -> ProjectOut:
    return ProjectOut(
        id=str(p.id),
        key=p.key,
        name=p.name,
        description=p.description,
        status=p.status,
        timezone=p.timezone,
        version=p.version,
    )


@router.get("", response_model=list[ProjectOut])
async def list_projects(actor: CurrentActor, db: DbSession) -> list[ProjectOut]:
    return [_out(p) for p in await projects.list_projects_for(db, actor)]


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    body: CreateProjectRequest, actor: CurrentActor, db: DbSession, ctx: RequestCtx, response: Response
) -> ProjectOut:
    project = await projects.create_project(
        db,
        actor,
        ctx,
        key=body.key,
        name=body.name,
        description=body.description,
        timezone=body.timezone,
    )
    response.headers["Location"] = f"/api/v1/projects/{project.id}"
    return _out(project)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: str, actor: CurrentActor, db: DbSession) -> ProjectOut:
    pid = uuid.UUID(project_id)
    authz.require_member(actor, pid)
    project = await db.get(Project, pid)
    from app.core.errors import ResourceNotFound

    if project is None:
        raise ResourceNotFound("Project not found.")
    return _out(project)


class ArchiveRequest(BaseModel):
    expected_version: int


@router.post("/{project_id}/archive", response_model=ProjectOut)
async def archive_project(
    project_id: str, body: ArchiveRequest, actor: CurrentActor, db: DbSession, ctx: RequestCtx
) -> ProjectOut:
    project = await projects.archive_project(
        db, actor, ctx, project_id=uuid.UUID(project_id), expected_version=body.expected_version
    )
    return _out(project)


class MembershipOut(BaseModel):
    user_id: str
    username: str
    role: str
    status: str


@router.get("/{project_id}/members", response_model=list[MembershipOut])
async def list_members(project_id: str, actor: CurrentActor, db: DbSession) -> list[MembershipOut]:
    pid = uuid.UUID(project_id)
    authz.require_member(actor, pid)
    rows = (
        await db.execute(
            select(ProjectMembership, User)
            .join(User, User.id == ProjectMembership.user_id)
            .where(ProjectMembership.project_id == pid, ProjectMembership.status == "active")
        )
    ).all()
    return [
        MembershipOut(user_id=str(m.user_id), username=u.username, role=m.role, status=m.status)
        for (m, u) in rows
    ]


@router.post("/{project_id}/members", response_model=MembershipOut, status_code=201)
async def add_member(
    project_id: str, body: MemberRequest, actor: CurrentActor, db: DbSession, ctx: RequestCtx
) -> MembershipOut:
    m = await projects.add_member(
        db, actor, ctx, project_id=uuid.UUID(project_id), role=body.role,
        user_id=uuid.UUID(body.user_id) if body.user_id else None,
        new_user=body.new_user.model_dump() if body.new_user else None,
    )
    u = await db.get(User, m.user_id)
    return MembershipOut(user_id=str(m.user_id), username=u.username if u else "", role=m.role, status=m.status)


@router.delete("/{project_id}/members/{user_id}", status_code=204)
async def remove_member(
    project_id: str, user_id: str, actor: CurrentActor, db: DbSession, ctx: RequestCtx
):
    await projects.remove_member(
        db, actor, ctx, project_id=uuid.UUID(project_id), user_id=uuid.UUID(user_id)
    )


class ReferenceOut(BaseModel):
    id: str
    kind: str
    value: str
    is_active: bool


@router.get("/{project_id}/reference-values", response_model=list[ReferenceOut])
async def list_reference_values(
    project_id: str, actor: CurrentActor, db: DbSession
) -> list[ReferenceOut]:
    pid = uuid.UUID(project_id)
    authz.require_member(actor, pid)
    rows = (
        await db.scalars(
            select(ReferenceValue)
            .where(ReferenceValue.project_id == pid)
            .order_by(ReferenceValue.kind, ReferenceValue.value)
        )
    ).all()
    return [
        ReferenceOut(id=str(r.id), kind=r.kind, value=r.value, is_active=r.is_active) for r in rows
    ]


@router.post("/{project_id}/reference-values", response_model=ReferenceOut, status_code=201)
async def add_reference_value(
    project_id: str, body: ReferenceRequest, actor: CurrentActor, db: DbSession, ctx: RequestCtx
) -> ReferenceOut:
    r = await projects.add_reference_value(
        db, actor, ctx, project_id=uuid.UUID(project_id), kind=body.kind, value=body.value
    )
    return ReferenceOut(id=str(r.id), kind=r.kind, value=r.value, is_active=r.is_active)
