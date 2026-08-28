"""Scenarios - the middle of the Requirement -> Scenario -> Test Case flow.

A scenario groups the test cases that exercise one requirement. It is an
organisational layer: coverage still resolves through it (a requirement is
covered when a scenario under it contains a qualifying test case).
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import Actor, Ctx
from app.core.errors import ResourceNotFound, StateTransitionNotAllowed, ValidationFailed
from app.domain import audit, authz
from app.domain.concurrency import check_version
from app.domain.keys import next_key
from app.domain.sorting import apply_sort, natural_key_order
from app.models import Project, Requirement, Scenario, TestCase


async def _project(session: AsyncSession, project_id: uuid.UUID) -> Project:
    p = await session.get(Project, project_id)
    if p is None:
        raise ResourceNotFound("Project not found.")
    return p


async def _check_requirement(session: AsyncSession, project_id: uuid.UUID, requirement_id: uuid.UUID | None):
    if requirement_id is None:
        return
    req = await session.get(Requirement, requirement_id)
    if req is None or req.project_id != project_id:
        raise ValidationFailed("Requirement not found in this project.")


async def create_scenario(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, project_id: uuid.UUID,
    title: str, description: str | None = None, requirement_id: uuid.UUID | None = None,
) -> Scenario:
    await _project(session, project_id)
    authz.authorize(actor, "test_case.create", project_id=project_id)
    if not title.strip():
        raise ValidationFailed("Title is required.")
    await _check_requirement(session, project_id, requirement_id)
    sc = Scenario(
        project_id=project_id, key=await next_key(session, project_id, "scenario"),
        title=title.strip(), description=description, requirement_id=requirement_id,
        owner_id=actor.id, created_by=actor.id, status="active",
    )
    session.add(sc)
    await session.flush()
    audit.record(session, actor=actor, ctx=ctx, entity_type="scenario", action="scenario.created",
                 entity_id=sc.id, entity_key=sc.key, project_id=project_id, after={"title": sc.title})
    await session.commit()
    return sc


async def update_scenario(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, scenario_id: uuid.UUID, expected_version: int,
    title: str | None = None, description: str | None = None,
    requirement_id: uuid.UUID | None = ...,  # type: ignore[assignment]
) -> Scenario:
    sc = await _get(session, scenario_id)
    authz.authorize(actor, "test_case.edit", project_id=sc.project_id, resource=sc)
    check_version(sc.version, expected_version, entity="scenario")
    if sc.status == "archived":
        raise StateTransitionNotAllowed("Restore the scenario before editing it.")
    if title is not None:
        sc.title = title.strip()
    if description is not None:
        sc.description = description
    if requirement_id is not ...:
        await _check_requirement(session, sc.project_id, requirement_id)
        sc.requirement_id = requirement_id
    sc.version += 1
    audit.record(session, actor=actor, ctx=ctx, entity_type="scenario", action="scenario.updated",
                 entity_id=sc.id, entity_key=sc.key, project_id=sc.project_id, after={"title": sc.title})
    await session.commit()
    return sc


async def set_status(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, scenario_id: uuid.UUID,
    expected_version: int, status: str,
) -> Scenario:
    sc = await _get(session, scenario_id)
    authz.authorize(actor, "test_case.delete", project_id=sc.project_id)
    check_version(sc.version, expected_version, entity="scenario")
    if status not in ("active", "archived"):
        raise ValidationFailed("status must be 'active' or 'archived'.")
    sc.status = status
    sc.version += 1
    audit.record(session, actor=actor, ctx=ctx, entity_type="scenario",
                 action=f"scenario.{status}", entity_id=sc.id, entity_key=sc.key, project_id=sc.project_id)
    await session.commit()
    return sc


async def set_test_case_scenario(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, test_case_id: uuid.UUID,
    scenario_id: uuid.UUID | None,
) -> TestCase:
    tc = await session.get(TestCase, test_case_id)
    if tc is None:
        raise ResourceNotFound("Test case not found.")
    authz.authorize(actor, "test_case.edit", project_id=tc.project_id, resource=tc)
    if scenario_id is not None:
        sc = await session.get(Scenario, scenario_id)
        if sc is None or sc.project_id != tc.project_id:
            raise ValidationFailed("Scenario not found in this project.")
        if sc.status == "archived":
            raise ValidationFailed("Cannot add a test case to an archived scenario.")
    before = str(tc.scenario_id) if tc.scenario_id else None
    tc.scenario_id = scenario_id
    audit.record(session, actor=actor, ctx=ctx, entity_type="test_case", action="test_case.scenario_changed",
                 entity_id=tc.id, entity_key=tc.key, project_id=tc.project_id,
                 before={"scenario_id": before}, after={"scenario_id": str(scenario_id) if scenario_id else None})
    await session.commit()
    return tc


async def list_scenarios(
    session: AsyncSession, actor: Actor, *, project_id: uuid.UUID,
    requirement_id: uuid.UUID | None = None, status: str | None = None,
    query: str | None = None, sort: str | None = None,
) -> list[Scenario]:
    authz.require_member(actor, project_id)
    stmt = select(Scenario).where(Scenario.project_id == project_id)
    if requirement_id is not None:
        stmt = stmt.where(Scenario.requirement_id == requirement_id)
    if status:
        stmt = stmt.where(Scenario.status == status)
    if query:
        like = f"%{query.lower()}%"
        stmt = stmt.where(func.lower(Scenario.title).like(like) | func.lower(Scenario.key).like(like))
    allowed = {
        "key": natural_key_order(Scenario),
        "title": [func.lower(Scenario.title)],
        "status": [Scenario.status],
    }
    stmt = apply_sort(stmt, sort=sort, allowed=allowed, default=natural_key_order(Scenario))
    return list(await session.scalars(stmt))


async def _get(session: AsyncSession, scenario_id: uuid.UUID) -> Scenario:
    sc = await session.get(Scenario, scenario_id)
    if sc is None:
        raise ResourceNotFound("Scenario not found.")
    return sc
