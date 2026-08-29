"""Lightweight Requirements, Releases, and Defects (increment 8, PRS §8.1).

Phase 1 = lightweight lifecycle + fields. Rich configurable workflows and external
synchronization are Phase 2.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import Actor, Ctx
from app.core.errors import ResourceNotFound, StateTransitionNotAllowed, ValidationFailed
from app.domain import audit, authz
from app.domain.concurrency import check_version
from app.domain.keys import next_key
from app.models import Defect, Project, Release, Requirement, Scenario, TraceLink

REQ_STATES = ("draft", "active", "fulfilled", "archived")
REQ_TRANSITIONS = {
    ("draft", "active"), ("active", "fulfilled"), ("fulfilled", "active"),
    ("active", "archived"), ("draft", "archived"), ("fulfilled", "archived"),
    ("archived", "draft"),
}
RELEASE_STATES = ("planned", "active", "released", "cancelled", "archived")
RELEASE_TRANSITIONS = {
    ("planned", "active"), ("active", "released"), ("planned", "cancelled"),
    ("active", "cancelled"), ("released", "archived"), ("cancelled", "archived"),
    ("planned", "archived"),
}
DEFECT_STATES = ("new", "open", "in_progress", "resolved", "closed", "rejected")
DEFECT_TRANSITIONS = {
    ("new", "open"), ("new", "rejected"), ("open", "in_progress"), ("open", "rejected"),
    ("in_progress", "resolved"), ("in_progress", "open"), ("resolved", "closed"),
    ("resolved", "open"), ("closed", "open"),
}
SEVERITIES = ("critical", "high", "major", "minor", "trivial")


async def _project(session: AsyncSession, project_id: uuid.UUID) -> Project:
    p = await session.get(Project, project_id)
    if p is None:
        raise ResourceNotFound("Project not found.")
    return p


async def _check_release(session: AsyncSession, project_id: uuid.UUID, release_id: uuid.UUID | None) -> None:
    if release_id is None:
        return
    rel = await session.get(Release, release_id)
    if rel is None or rel.project_id != project_id:
        raise ValidationFailed("Release not found in this project (cross-project links rejected).")


# --------------------------------------------------------------------------- requirements


async def create_requirement(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, project_id: uuid.UUID,
    title: str, description: str | None = None, req_type: str = "functional",
    priority: str = "medium", component: str | None = None, release_id: uuid.UUID | None = None,
) -> Requirement:
    await _project(session, project_id)
    authz.authorize(actor, "requirement.manage", project_id=project_id)
    await _check_release(session, project_id, release_id)
    req = Requirement(
        project_id=project_id, key=await next_key(session, project_id, "requirement"),
        title=title.strip(), description=description, req_type=req_type, priority=priority,
        component=component, release_id=release_id, owner_id=actor.id, created_by=actor.id,
        status="draft",
    )
    session.add(req)
    await session.flush()
    audit.record(session, actor=actor, ctx=ctx, entity_type="requirement", action="requirement.created",
                 entity_id=req.id, entity_key=req.key, project_id=project_id, after={"title": req.title})
    await session.commit()
    return req


_PRIORITIES = ("critical", "high", "medium", "low")
_REQ_TYPES = ("functional", "non_functional", "compliance", "ux", "performance")


async def update_requirement(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, requirement_id: uuid.UUID,
    expected_version: int, title: str | None = None, description: str | None = None,
    priority: str | None = None, req_type: str | None = None,
) -> Requirement:
    req = await session.get(Requirement, requirement_id)
    if req is None:
        raise ResourceNotFound("Requirement not found.")
    authz.authorize(actor, "requirement.manage", project_id=req.project_id)
    check_version(req.version, expected_version, entity="requirement")
    if title is not None:
        if not title.strip():
            raise ValidationFailed("Title must not be empty.")
        req.title = title.strip()
    if description is not None:
        req.description = description or None
    if priority is not None:
        if priority not in _PRIORITIES:
            raise ValidationFailed(f"Invalid priority '{priority}'.")
        req.priority = priority
    if req_type is not None:
        req.req_type = req_type
    req.version += 1
    audit.record(session, actor=actor, ctx=ctx, entity_type="requirement", action="requirement.updated",
                 entity_id=req.id, entity_key=req.key, project_id=req.project_id, after={"title": req.title})
    await session.commit()
    return req


async def delete_requirement(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, requirement_id: uuid.UUID
) -> None:
    req = await session.get(Requirement, requirement_id)
    if req is None:
        raise ResourceNotFound("Requirement not found.")
    authz.authorize(actor, "requirement.delete", project_id=req.project_id)
    await session.execute(
        delete(TraceLink).where(
            or_(
                and_(TraceLink.source_type == "requirement", TraceLink.source_id == req.id),
                and_(TraceLink.target_type == "requirement", TraceLink.target_id == req.id),
            )
        )
    )
    await session.execute(
        update(Scenario).where(Scenario.requirement_id == req.id).values(requirement_id=None)
    )
    audit.record(session, actor=actor, ctx=ctx, entity_type="requirement", action="requirement.deleted",
                 entity_id=req.id, entity_key=req.key, project_id=req.project_id,
                 before={"title": req.title})
    await session.delete(req)
    await session.commit()


async def transition_requirement(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, requirement_id: uuid.UUID,
    to_status: str, expected_version: int,
) -> Requirement:
    req = await session.get(Requirement, requirement_id)
    if req is None:
        raise ResourceNotFound("Requirement not found.")
    authz.authorize(actor, "requirement.manage", project_id=req.project_id)
    check_version(req.version, expected_version, entity="requirement")
    if (req.status, to_status) not in REQ_TRANSITIONS:
        raise StateTransitionNotAllowed(f"Cannot move requirement from '{req.status}' to '{to_status}'.")
    before = req.status
    req.status = to_status
    req.version += 1
    audit.record(session, actor=actor, ctx=ctx, entity_type="requirement",
                 action=f"requirement.{to_status}", entity_id=req.id, entity_key=req.key,
                 project_id=req.project_id, before={"status": before}, after={"status": to_status})
    await session.commit()
    return req


# --------------------------------------------------------------------------- releases


async def create_release(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, project_id: uuid.UUID,
    name: str, description: str | None = None, version_label: str | None = None,
    start_date: datetime | None = None, end_date: datetime | None = None,
) -> Release:
    await _project(session, project_id)
    authz.authorize(actor, "release.manage", project_id=project_id)
    rel = Release(
        project_id=project_id, key=await next_key(session, project_id, "release"),
        name=name.strip(), description=description, version_label=version_label,
        start_date=start_date, end_date=end_date,
        owner_id=actor.id, created_by=actor.id, status="planned",
    )
    session.add(rel)
    await session.flush()
    audit.record(session, actor=actor, ctx=ctx, entity_type="release", action="release.created",
                 entity_id=rel.id, entity_key=rel.key, project_id=project_id, after={"name": rel.name})
    await session.commit()
    return rel


async def update_release(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, release_id: uuid.UUID, expected_version: int,
    name: str | None = None, description: str | None = None, version_label: str | None = None,
    start_date: datetime | None = ..., end_date: datetime | None = ...,  # type: ignore[assignment]
) -> Release:
    rel = await session.get(Release, release_id)
    if rel is None:
        raise ResourceNotFound("Release not found.")
    authz.authorize(actor, "release.manage", project_id=rel.project_id)
    check_version(rel.version, expected_version, entity="release")
    if name is not None:
        rel.name = name.strip()
    if description is not None:
        rel.description = description
    if version_label is not None:
        rel.version_label = version_label or None
    if start_date is not ...:
        rel.start_date = start_date
    if end_date is not ...:
        rel.end_date = end_date
    if rel.start_date and rel.end_date and rel.end_date < rel.start_date:
        raise ValidationFailed("End date cannot be before the start date.")
    rel.version += 1
    audit.record(session, actor=actor, ctx=ctx, entity_type="release", action="release.updated",
                 entity_id=rel.id, entity_key=rel.key, project_id=rel.project_id, after={"name": rel.name})
    await session.commit()
    return rel


async def transition_release(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, release_id: uuid.UUID,
    to_status: str, expected_version: int,
) -> Release:
    rel = await session.get(Release, release_id)
    if rel is None:
        raise ResourceNotFound("Release not found.")
    authz.authorize(actor, "release.manage", project_id=rel.project_id)
    check_version(rel.version, expected_version, entity="release")
    if (rel.status, to_status) not in RELEASE_TRANSITIONS:
        raise StateTransitionNotAllowed(f"Cannot move release from '{rel.status}' to '{to_status}'.")
    before = rel.status
    rel.status = to_status
    rel.version += 1
    audit.record(session, actor=actor, ctx=ctx, entity_type="release", action=f"release.{to_status}",
                 entity_id=rel.id, entity_key=rel.key, project_id=rel.project_id,
                 before={"status": before}, after={"status": to_status})
    await session.commit()
    return rel


# --------------------------------------------------------------------------- defects


async def create_defect(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, project_id: uuid.UUID,
    summary: str, description: str | None = None, severity: str = "major",
    priority: str = "medium", environment: str | None = None, release_id: uuid.UUID | None = None,
    detected_build: str | None = None,
) -> Defect:
    await _project(session, project_id)
    authz.authorize(actor, "defect.manage", project_id=project_id)
    await _check_release(session, project_id, release_id)
    if severity not in SEVERITIES:
        raise ValidationFailed(f"Invalid severity '{severity}'.")
    d = Defect(
        project_id=project_id, key=await next_key(session, project_id, "defect"),
        summary=summary.strip(), description=description, severity=severity, priority=priority,
        environment=environment, release_id=release_id, detected_build=detected_build,
        reporter_id=actor.id, created_by=actor.id, status="new",
    )
    session.add(d)
    await session.flush()
    audit.record(session, actor=actor, ctx=ctx, entity_type="defect", action="defect.created",
                 entity_id=d.id, entity_key=d.key, project_id=project_id,
                 after={"summary": d.summary, "severity": severity})
    await session.commit()
    return d


async def transition_defect(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, defect_id: uuid.UUID,
    to_status: str, expected_version: int, resolution: str | None = None,
    resolved_build: str | None = None,
) -> Defect:
    d = await session.get(Defect, defect_id)
    if d is None:
        raise ResourceNotFound("Defect not found.")
    authz.authorize(actor, "defect.manage", project_id=d.project_id)
    check_version(d.version, expected_version, entity="defect")
    if (d.status, to_status) not in DEFECT_TRANSITIONS:
        raise StateTransitionNotAllowed(f"Cannot move defect from '{d.status}' to '{to_status}'.")
    before = d.status
    d.status = to_status
    if to_status == "resolved":
        d.resolution = resolution
        d.resolved_build = resolved_build
    d.version += 1
    audit.record(session, actor=actor, ctx=ctx, entity_type="defect", action=f"defect.{to_status}",
                 entity_id=d.id, entity_key=d.key, project_id=d.project_id,
                 before={"status": before}, after={"status": to_status})
    await session.commit()
    return d


async def list_entities(
    session: AsyncSession, model, project_id: uuid.UUID, page: int, page_size: int,
    sort: str | None = None,
):
    from app.domain.sorting import apply_sort, natural_key_order

    stmt = select(model).where(model.project_id == project_id)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    allowed: dict = {"key": natural_key_order(model), "status": [model.status]}
    for name in ("title", "name", "summary", "priority", "severity", "created_at", "updated_at"):
        col = getattr(model, name, None)
        if col is not None:
            allowed[name] = [func.lower(col)] if name in ("title", "name", "summary") else [col]
    stmt = apply_sort(stmt, sort=sort, allowed=allowed, default=natural_key_order(model))
    rows = (await session.scalars(stmt.limit(page_size).offset((page - 1) * page_size))).all()
    return list(rows), int(total)
