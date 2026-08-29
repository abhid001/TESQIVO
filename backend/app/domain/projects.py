"""Project, membership, and reference-data services (increment 3).

Creating a project seeds default reference data. The creator is added as
project_admin. Default RBAC roles are fixed in Phase 1 (PRS §10).
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import Actor, Ctx, Role
from app.core.errors import DuplicateResource, Forbidden, ResourceNotFound, ValidationFailed
from app.domain import audit, authz
from app.domain.concurrency import check_version
from app.models import (
    AuditEvent,
    Defect,
    EntityCounter,
    Project,
    ProjectAccessRequest,
    ProjectMembership,
    ReferenceValue,
    Release,
    Requirement,
    Scenario,
    TestCase,
    TestCycle,
    TestFolder,
    TestPlan,
    User,
)

_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]{1,15}$")
_DEFAULT_REFS = {
    "environment": ["development", "staging", "production"],
    "test_type": ["functional", "regression", "smoke", "integration"],
    "component": [],
    "tag": [],
    "attachment_policy": ["default"],
}


def _now() -> datetime:
    return datetime.now(UTC)


async def create_project(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    key: str,
    name: str,
    description: str | None = None,
    timezone: str = "UTC",
) -> Project:
    if not actor.is_system_admin:
        # Only system admins create projects in Phase 1.
        from app.core.errors import Forbidden

        raise Forbidden("System administrator access required to create a project.")
    key = key.strip().upper()
    if not _KEY_RE.match(key):
        raise ValidationFailed(
            "Project key must be 2-16 chars, uppercase letters/digits, starting with a letter.",
            details=[{"field": "/key", "code": "INVALID", "message": "Invalid project key."}],
        )
    if await session.scalar(select(Project).where(Project.key == key)):
        raise DuplicateResource(f"Project key '{key}' is already in use.")
    project = Project(
        key=key,
        name=name.strip(),
        description=description,
        timezone=timezone or "UTC",
        created_by=actor.id,
        status="active",
    )
    session.add(project)
    await session.flush()

    session.add(
        ProjectMembership(
            project_id=project.id,
            user_id=actor.id,
            role=Role.project_admin.value,
            added_by=actor.id,
        )
    )
    for kind, values in _DEFAULT_REFS.items():
        for v in values:
            session.add(ReferenceValue(project_id=project.id, kind=kind, value=v))

    audit.record(
        session,
        actor=actor,
        ctx=ctx,
        entity_type="project",
        action="project.created",
        entity_id=project.id,
        entity_key=project.key,
        project_id=project.id,
        after={"key": project.key, "name": project.name},
    )
    await session.commit()
    return project


async def archive_project(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, project_id: uuid.UUID, expected_version: int
) -> Project:
    project = await _get_project(session, project_id)
    authz.authorize(actor, "project.settings", project_id=project_id)
    check_version(project.version, expected_version, entity="project")
    project.status = "archived"
    project.version += 1
    audit.record(
        session,
        actor=actor,
        ctx=ctx,
        entity_type="project",
        action="project.archived",
        entity_id=project.id,
        entity_key=project.key,
        project_id=project.id,
    )
    await session.commit()
    return project


async def update_project(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, project_id: uuid.UUID,
    expected_version: int, name: str | None = None, description: str | None = None,
) -> Project:
    project = await _get_project(session, project_id)
    authz.authorize(actor, "project.settings", project_id=project_id)
    check_version(project.version, expected_version, entity="project")
    if name is not None:
        if not name.strip():
            raise ValidationFailed("Name must not be empty.")
        project.name = name.strip()
    if description is not None:
        project.description = description or None
    project.version += 1
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="project", action="project.updated",
        entity_id=project.id, entity_key=project.key, project_id=project.id, after={"name": project.name},
    )
    await session.commit()
    return project


async def delete_project(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, project_id: uuid.UUID
) -> None:
    if not actor.is_system_admin:
        raise Forbidden("System administrator access required to delete a project.")
    project = await _get_project(session, project_id)
    if project.status != "archived":
        raise ValidationFailed("Archive the project before deleting it.")
    for model in (Requirement, TestCase, TestCycle, TestPlan, Release, Defect, Scenario, TestFolder):
        if await session.scalar(
            select(func.count()).select_from(model).where(model.project_id == project_id)
        ):
            raise ValidationFailed(
                "This project still contains data (requirements, tests, cycles, …). "
                "Only an empty archived project can be deleted."
            )
    await session.execute(delete(ReferenceValue).where(ReferenceValue.project_id == project_id))
    await session.execute(delete(ProjectMembership).where(ProjectMembership.project_id == project_id))
    await session.execute(delete(ProjectAccessRequest).where(ProjectAccessRequest.project_id == project_id))
    await session.execute(delete(EntityCounter).where(EntityCounter.project_id == project_id))
    await session.execute(delete(AuditEvent).where(AuditEvent.project_id == project_id))
    key = project.key
    await session.delete(project)
    await session.flush()
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="project", action="project.deleted",
        entity_id=project_id, entity_key=key, before={"key": key},
    )
    await session.commit()


async def add_member(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    project_id: uuid.UUID,
    role: str,
    user_id: uuid.UUID | None = None,
    new_user: dict | None = None,
) -> ProjectMembership:
    """Add a user to a project. Either `user_id` (existing user) or `new_user`
    (``{username, email, display_name, password}``) - a project admin can provision
    a plain (non-system-admin) user for their project."""
    await _get_project(session, project_id)
    authz.authorize(actor, "membership.manage", project_id=project_id)
    try:
        Role(role)
    except ValueError:
        raise ValidationFailed(f"Unknown role '{role}'.") from None

    if new_user is not None:
        from app.domain.auth import provision_user

        target = await provision_user(
            session, ctx,
            username=new_user["username"], email=new_user["email"],
            display_name=new_user.get("display_name") or new_user["username"],
            password=new_user["password"],
        )
        user_id = target.id
    else:
        if user_id is None:
            raise ValidationFailed("Provide an existing user or details for a new user.")
        target = await session.get(User, user_id)
    if target is None:
        raise ResourceNotFound("User not found.")
    if target.status == "disabled":
        raise ValidationFailed("Cannot add a disabled user to a project.")
    existing = await session.scalar(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user_id,
            ProjectMembership.status == "active",
        )
    )
    if existing is not None:
        existing.role = role
        audit.record(
            session,
            actor=actor,
            ctx=ctx,
            entity_type="project_membership",
            action="membership.role_changed",
            entity_id=existing.id,
            project_id=project_id,
            after={"user_id": str(user_id), "role": role},
        )
        await session.commit()
        return existing
    membership = ProjectMembership(
        project_id=project_id, user_id=user_id, role=role, added_by=actor.id
    )
    session.add(membership)
    await session.flush()
    audit.record(
        session,
        actor=actor,
        ctx=ctx,
        entity_type="project_membership",
        action="membership.added",
        entity_id=membership.id,
        project_id=project_id,
        after={"user_id": str(user_id), "role": role},
    )
    await session.commit()
    return membership


async def remove_member(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, project_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    await _get_project(session, project_id)
    authz.authorize(actor, "membership.manage", project_id=project_id)
    membership = await session.scalar(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user_id,
            ProjectMembership.status == "active",
        )
    )
    if membership is None:
        raise ResourceNotFound("Membership not found.")
    membership.status = "removed"
    membership.removed_by = actor.id
    membership.removed_at = _now()
    audit.record(
        session,
        actor=actor,
        ctx=ctx,
        entity_type="project_membership",
        action="membership.removed",
        entity_id=membership.id,
        project_id=project_id,
        before={"user_id": str(user_id), "role": membership.role},
    )
    await session.commit()


async def add_reference_value(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    project_id: uuid.UUID,
    kind: str,
    value: str,
) -> ReferenceValue:
    await _get_project(session, project_id)
    authz.authorize(actor, "reference.manage", project_id=project_id)
    if kind not in _DEFAULT_REFS:
        raise ValidationFailed(f"Unknown reference kind '{kind}'.")
    value = value.strip()
    if not value:
        raise ValidationFailed("Reference value must not be empty.")
    dupe = await session.scalar(
        select(ReferenceValue).where(
            ReferenceValue.project_id == project_id,
            ReferenceValue.kind == kind,
            ReferenceValue.value == value,
        )
    )
    if dupe is not None:
        raise DuplicateResource("That reference value already exists.")
    rv = ReferenceValue(project_id=project_id, kind=kind, value=value)
    session.add(rv)
    await session.flush()
    audit.record(
        session,
        actor=actor,
        ctx=ctx,
        entity_type="reference_value",
        action="reference.added",
        entity_id=rv.id,
        project_id=project_id,
        after={"kind": kind, "value": value},
    )
    await session.commit()
    return rv


async def remove_reference_value(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, ref_id: uuid.UUID
) -> None:
    rv = await session.get(ReferenceValue, ref_id)
    if rv is None:
        raise ResourceNotFound("Reference value not found.")
    authz.authorize(actor, "reference.manage", project_id=rv.project_id)
    audit.record(
        session,
        actor=actor,
        ctx=ctx,
        entity_type="reference_value",
        action="reference.removed",
        entity_id=rv.id,
        project_id=rv.project_id,
        before={"kind": rv.kind, "value": rv.value},
    )
    await session.delete(rv)
    await session.commit()


async def list_projects_for(session: AsyncSession, actor: Actor) -> list[Project]:
    stmt = select(Project).order_by(Project.key)
    if not actor.is_system_admin:
        stmt = stmt.where(Project.id.in_(list(actor.memberships.keys()) or [uuid.UUID(int=0)]))
    return list((await session.scalars(stmt)).all())


async def _get_project(session: AsyncSession, project_id: uuid.UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise ResourceNotFound("Project not found.")
    return project


async def count_projects(session: AsyncSession) -> int:
    return (await session.scalar(select(func.count()).select_from(Project))) or 0
