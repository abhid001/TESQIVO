"""Project access requests.

A signed-in user can browse every active project and ask for access to one they are
not a member of. A project admin (or system admin) approves or denies the request;
approval grants membership at the decided role.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import Actor, Ctx, Role
from app.core.errors import Forbidden, ResourceNotFound, ValidationFailed
from app.domain import audit, authz, projects
from app.models import Project, ProjectAccessRequest, ProjectMembership, User

_REQUESTABLE_ROLES = {Role.tester.value, Role.viewer.value, Role.test_manager.value}


def _now() -> datetime:
    return datetime.now(UTC)


async def list_discoverable(
    session: AsyncSession, actor: Actor
) -> list[tuple[Project, bool, str | None]]:
    """Every active project, with (is_member, pending_request_role)."""
    rows = list(
        (
            await session.scalars(
                select(Project).where(Project.status == "active").order_by(Project.key)
            )
        ).all()
    )
    member_ids = set(actor.memberships.keys())
    pending = dict((
            await session.execute(
                select(
                    ProjectAccessRequest.project_id, ProjectAccessRequest.requested_role
                ).where(
                    ProjectAccessRequest.user_id == actor.id,
                    ProjectAccessRequest.status == "pending",
                )
            )
        ).all())
    return [(p, p.id in member_ids, pending.get(p.id)) for p in rows]


async def request_access(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    project_id: uuid.UUID,
    requested_role: str = "tester",
    message: str | None = None,
) -> ProjectAccessRequest:
    project = await session.get(Project, project_id)
    if project is None or project.status != "active":
        raise ResourceNotFound("Project not found.")
    if project_id in actor.memberships or actor.is_system_admin:
        raise ValidationFailed("You already have access to this project.")
    if requested_role not in _REQUESTABLE_ROLES:
        requested_role = Role.tester.value
    existing = await session.scalar(
        select(ProjectAccessRequest).where(
            ProjectAccessRequest.user_id == actor.id,
            ProjectAccessRequest.project_id == project_id,
            ProjectAccessRequest.status == "pending",
        )
    )
    if existing is not None:
        return existing
    req = ProjectAccessRequest(
        user_id=actor.id,
        project_id=project_id,
        requested_role=requested_role,
        message=(message or "").strip()[:2000] or None,
    )
    session.add(req)
    await session.flush()
    audit.record(
        session,
        actor=actor,
        ctx=ctx,
        entity_type="project_access_request",
        action="access_request.created",
        entity_id=req.id,
        project_id=project_id,
        after={"requested_role": requested_role},
    )
    await session.commit()
    return req


async def list_requests(
    session: AsyncSession,
    actor: Actor,
    *,
    project_id: uuid.UUID | None = None,
    status: str = "pending",
) -> list[tuple[ProjectAccessRequest, User, Project]]:
    stmt = (
        select(ProjectAccessRequest, User, Project)
        .join(User, User.id == ProjectAccessRequest.user_id)
        .join(Project, Project.id == ProjectAccessRequest.project_id)
        .order_by(ProjectAccessRequest.created_at.desc())
    )
    if status in ("pending", "approved", "denied"):
        stmt = stmt.where(ProjectAccessRequest.status == status)
    if project_id is not None:
        authz.authorize(actor, "membership.manage", project_id=project_id)
        stmt = stmt.where(ProjectAccessRequest.project_id == project_id)
    elif not actor.is_system_admin:
        # Non-admins only see requests for projects they administer.
        admin_pids = [
            pid for pid, m in actor.memberships.items() if m.role == Role.project_admin
        ]
        if not admin_pids:
            raise Forbidden("You do not administer any project.")
        stmt = stmt.where(ProjectAccessRequest.project_id.in_(admin_pids))
    return list((await session.execute(stmt)).all())


async def decide_request(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    request_id: uuid.UUID,
    approve: bool,
    role: str | None = None,
) -> ProjectAccessRequest:
    req = await session.get(ProjectAccessRequest, request_id)
    if req is None:
        raise ResourceNotFound("Access request not found.")
    authz.authorize(actor, "membership.manage", project_id=req.project_id)
    if req.status != "pending":
        raise ValidationFailed("This request has already been decided.")
    granted_role = role or req.requested_role
    if approve:
        # add_member runs its own authz + commit
        await projects.add_member(
            session, actor, ctx, project_id=req.project_id, role=granted_role, user_id=req.user_id
        )
    req = await session.get(ProjectAccessRequest, request_id)
    req.status = "approved" if approve else "denied"
    req.decided_by = actor.id
    req.decided_at = _now()
    if approve:
        req.requested_role = granted_role
    audit.record(
        session,
        actor=actor,
        ctx=ctx,
        entity_type="project_access_request",
        action="access_request.approved" if approve else "access_request.denied",
        entity_id=req.id,
        project_id=req.project_id,
        after={"role": granted_role} if approve else None,
    )
    await session.commit()
    return req


async def user_memberships(
    session: AsyncSession, actor: Actor, *, user_id: uuid.UUID
) -> list[tuple[ProjectMembership, Project]]:
    if not actor.is_system_admin:
        raise Forbidden("System administrator access required.")
    rows = (
        await session.execute(
            select(ProjectMembership, Project)
            .join(Project, Project.id == ProjectMembership.project_id)
            .where(
                ProjectMembership.user_id == user_id,
                ProjectMembership.status == "active",
            )
            .order_by(Project.key)
        )
    ).all()
    return list(rows)
