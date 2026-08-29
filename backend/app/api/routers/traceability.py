"""Requirements, releases, defects, trace links, and the matrix (increment 8)."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.deps import CurrentActor, DbSession, RequestCtx
from app.domain import authz, backlog, traceability
from app.models import Defect, Release, Requirement

router = APIRouter(tags=["traceability"])


# --- requirements ---
class CreateRequirement(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    req_type: str = "functional"
    priority: str = "medium"
    component: str | None = None
    release_id: str | None = None


class UpdateRequirement(BaseModel):
    expected_version: int
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    req_type: str | None = None


class CreateRelease(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    version_label: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


class UpdateRelease(BaseModel):
    expected_version: int
    name: str | None = None
    description: str | None = None
    version_label: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    clear_start_date: bool = False
    clear_end_date: bool = False


class CreateDefect(BaseModel):
    summary: str = Field(min_length=1, max_length=300)
    description: str | None = None
    severity: str = "major"
    priority: str = "medium"
    environment: str | None = None
    release_id: str | None = None
    detected_build: str | None = None


class Transition(BaseModel):
    to: str
    expected_version: int
    resolution: str | None = None
    resolved_build: str | None = None


class CreateLink(BaseModel):
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    external_reference: str | None = None


def _req_out(r: Requirement) -> dict:
    return {"id": str(r.id), "key": r.key, "title": r.title, "status": r.status,
            "priority": r.priority, "req_type": r.req_type,
            "release_id": str(r.release_id) if r.release_id else None, "version": r.version}


def _rel_out(r: Release) -> dict:
    return {"id": str(r.id), "key": r.key, "name": r.name, "status": r.status,
            "description": r.description, "version_label": r.version_label,
            "start_date": r.start_date.isoformat() if r.start_date else None,
            "end_date": r.end_date.isoformat() if r.end_date else None,
            "version": r.version}


def _def_out(d: Defect) -> dict:
    return {"id": str(d.id), "key": d.key, "summary": d.summary, "status": d.status,
            "severity": d.severity, "priority": d.priority,
            "release_id": str(d.release_id) if d.release_id else None, "version": d.version}


@router.post("/projects/{project_id}/requirements", status_code=201)
async def create_requirement(project_id: str, body: CreateRequirement, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> dict:
    r = await backlog.create_requirement(
        db, actor, ctx, project_id=uuid.UUID(project_id), title=body.title, description=body.description,
        req_type=body.req_type, priority=body.priority, component=body.component,
        release_id=uuid.UUID(body.release_id) if body.release_id else None,
    )
    return _req_out(r)


def _page(items: list, page: int, page_size: int, total: int) -> dict:
    return {
        "items": items, "page": page, "page_size": page_size, "total": total,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


@router.get("/projects/{project_id}/requirements")
async def list_requirements(project_id: str, actor: CurrentActor, db: DbSession,
                            sort: str | None = None,
                            page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)) -> dict:
    pid = uuid.UUID(project_id)
    authz.require_member(actor, pid)
    rows, total = await backlog.list_entities(db, Requirement, pid, page, page_size, sort=sort)
    return _page([_req_out(r) for r in rows], page, page_size, total)


@router.post("/requirements/{req_id}/transitions")
async def transition_requirement(req_id: str, body: Transition, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> dict:
    r = await backlog.transition_requirement(
        db, actor, ctx, requirement_id=uuid.UUID(req_id), to_status=body.to, expected_version=body.expected_version
    )
    return _req_out(r)


@router.patch("/requirements/{req_id}")
async def update_requirement(req_id: str, body: UpdateRequirement, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> dict:
    r = await backlog.update_requirement(
        db, actor, ctx, requirement_id=uuid.UUID(req_id), expected_version=body.expected_version,
        title=body.title, description=body.description, priority=body.priority, req_type=body.req_type,
    )
    return _req_out(r)


@router.delete("/requirements/{req_id}", status_code=204)
async def delete_requirement(req_id: str, actor: CurrentActor, db: DbSession, ctx: RequestCtx):
    await backlog.delete_requirement(db, actor, ctx, requirement_id=uuid.UUID(req_id))


@router.post("/projects/{project_id}/releases", status_code=201)
async def create_release(project_id: str, body: CreateRelease, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> dict:
    r = await backlog.create_release(
        db, actor, ctx, project_id=uuid.UUID(project_id), name=body.name,
        description=body.description, version_label=body.version_label,
        start_date=body.start_date, end_date=body.end_date,
    )
    return _rel_out(r)


@router.get("/projects/{project_id}/releases")
async def list_releases(project_id: str, actor: CurrentActor, db: DbSession,
                        sort: str | None = None,
                        page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)) -> dict:
    pid = uuid.UUID(project_id)
    authz.require_member(actor, pid)
    rows, total = await backlog.list_entities(db, Release, pid, page, page_size, sort=sort)
    return _page([_rel_out(r) for r in rows], page, page_size, total)


@router.get("/releases/{release_id}")
async def get_release(release_id: str, actor: CurrentActor, db: DbSession) -> dict:
    r = await db.get(Release, uuid.UUID(release_id))
    from app.core.errors import ResourceNotFound

    if r is None:
        raise ResourceNotFound("Release not found.")
    authz.require_member(actor, r.project_id)
    return _rel_out(r)


@router.patch("/releases/{release_id}")
async def update_release(release_id: str, body: UpdateRelease, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> dict:
    kwargs: dict = dict(
        release_id=uuid.UUID(release_id), expected_version=body.expected_version,
        name=body.name, description=body.description, version_label=body.version_label,
    )
    if body.clear_start_date:
        kwargs["start_date"] = None
    elif body.start_date is not None:
        kwargs["start_date"] = body.start_date
    if body.clear_end_date:
        kwargs["end_date"] = None
    elif body.end_date is not None:
        kwargs["end_date"] = body.end_date
    r = await backlog.update_release(db, actor, ctx, **kwargs)
    return _rel_out(r)


@router.post("/releases/{release_id}/transitions")
async def transition_release(release_id: str, body: Transition, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> dict:
    r = await backlog.transition_release(
        db, actor, ctx, release_id=uuid.UUID(release_id), to_status=body.to, expected_version=body.expected_version
    )
    return _rel_out(r)


@router.post("/projects/{project_id}/defects", status_code=201)
async def create_defect(project_id: str, body: CreateDefect, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> dict:
    d = await backlog.create_defect(
        db, actor, ctx, project_id=uuid.UUID(project_id), summary=body.summary, description=body.description,
        severity=body.severity, priority=body.priority, environment=body.environment,
        release_id=uuid.UUID(body.release_id) if body.release_id else None, detected_build=body.detected_build,
    )
    return _def_out(d)


@router.get("/projects/{project_id}/defects")
async def list_defects(project_id: str, actor: CurrentActor, db: DbSession,
                       sort: str | None = None,
                       page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)) -> dict:
    pid = uuid.UUID(project_id)
    authz.require_member(actor, pid)
    rows, total = await backlog.list_entities(db, Defect, pid, page, page_size, sort=sort)
    return _page([_def_out(d) for d in rows], page, page_size, total)


@router.post("/defects/{defect_id}/transitions")
async def transition_defect(defect_id: str, body: Transition, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> dict:
    d = await backlog.transition_defect(
        db, actor, ctx, defect_id=uuid.UUID(defect_id), to_status=body.to,
        expected_version=body.expected_version, resolution=body.resolution, resolved_build=body.resolved_build,
    )
    return _def_out(d)


# --- links + matrix ---
@router.post("/projects/{project_id}/trace-links", status_code=201)
async def create_link(project_id: str, body: CreateLink, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> dict:
    link = await traceability.create_link(
        db, actor, ctx, project_id=uuid.UUID(project_id), source_type=body.source_type,
        source_id=uuid.UUID(body.source_id), target_type=body.target_type,
        target_id=uuid.UUID(body.target_id), external_reference=body.external_reference,
    )
    return {"id": str(link.id), "relationship_type": link.relationship_type}


@router.get("/projects/{project_id}/trace-links")
async def list_links(project_id: str, actor: CurrentActor, db: DbSession,
                     entity_type: str | None = None, entity_id: str | None = None,
                     include_removed: bool = False) -> dict:
    links = await traceability.list_links(
        db, actor, project_id=uuid.UUID(project_id), entity_type=entity_type,
        entity_id=uuid.UUID(entity_id) if entity_id else None, include_removed=include_removed,
    )
    return {"items": [
        {"id": str(l.id), "source_type": l.source_type, "source_id": str(l.source_id),
         "target_type": l.target_type, "target_id": str(l.target_id),
         "relationship_type": l.relationship_type, "origin": l.origin,
         "removed": l.removed_at is not None}
        for l in links
    ]}


@router.delete("/trace-links/{link_id}", status_code=204)
async def remove_link(link_id: str, actor: CurrentActor, db: DbSession, ctx: RequestCtx):
    await traceability.remove_link(db, actor, ctx, link_id=uuid.UUID(link_id))


@router.get("/projects/{project_id}/traceability/matrix")
async def matrix(project_id: str, actor: CurrentActor, db: DbSession,
                 release_id: str | None = None, cycle_id: str | None = None) -> dict:
    rows = await traceability.build_matrix(
        db, actor, project_id=uuid.UUID(project_id),
        release_id=uuid.UUID(release_id) if release_id else None,
        cycle_id=uuid.UUID(cycle_id) if cycle_id else None,
    )
    return {"rows": [
        {"requirement_key": r.requirement_key, "requirement_title": r.requirement_title,
         "requirement_status": r.requirement_status, "linked_test_case_keys": r.linked_test_case_keys,
         "planned_version_labels": r.planned_version_labels, "latest_results": r.latest_results}
        for r in rows
    ]}
