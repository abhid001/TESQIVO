"""Scenarios (Requirement -> Scenario -> Test Case)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import CurrentActor, DbSession, RequestCtx
from app.core.errors import ResourceNotFound
from app.domain import authz, scenarios
from app.domain.sorting import natural_key_order
from app.models import Scenario, TestCase

router = APIRouter(tags=["scenarios"])


class CreateScenario(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    requirement_id: str | None = None


class UpdateScenario(BaseModel):
    expected_version: int
    title: str | None = None
    description: str | None = None
    requirement_id: str | None = None
    clear_requirement: bool = False


class StatusRequest(BaseModel):
    expected_version: int
    status: str


class AssignRequest(BaseModel):
    test_case_id: str
    scenario_id: str | None = None


def _out(s: Scenario, test_count: int = 0) -> dict:
    return {
        "id": str(s.id), "key": s.key, "title": s.title, "description": s.description,
        "status": s.status, "requirement_id": str(s.requirement_id) if s.requirement_id else None,
        "test_count": test_count, "version": s.version,
    }


@router.post("/projects/{project_id}/scenarios", status_code=201)
async def create_scenario(project_id: str, body: CreateScenario, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> dict:
    s = await scenarios.create_scenario(
        db, actor, ctx, project_id=uuid.UUID(project_id), title=body.title,
        description=body.description,
        requirement_id=uuid.UUID(body.requirement_id) if body.requirement_id else None,
    )
    return _out(s)


@router.get("/projects/{project_id}/scenarios")
async def list_scenarios(
    project_id: str, actor: CurrentActor, db: DbSession,
    requirement_id: str | None = None, status: str | None = None,
    q: str | None = None, sort: str | None = None,
) -> dict:
    rows = await scenarios.list_scenarios(
        db, actor, project_id=uuid.UUID(project_id),
        requirement_id=uuid.UUID(requirement_id) if requirement_id else None,
        status=status, query=q, sort=sort,
    )
    counts = dict(
        (
            await db.execute(
                select(TestCase.scenario_id, func.count())
                .where(TestCase.project_id == uuid.UUID(project_id), TestCase.scenario_id.isnot(None))
                .group_by(TestCase.scenario_id)
            )
        ).all()
    )
    return {"items": [_out(s, counts.get(s.id, 0)) for s in rows]}


@router.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str, actor: CurrentActor, db: DbSession) -> dict:
    s = await db.get(Scenario, uuid.UUID(scenario_id))
    if s is None:
        raise ResourceNotFound("Scenario not found.")
    authz.require_member(actor, s.project_id)
    n = await db.scalar(select(func.count()).select_from(TestCase).where(TestCase.scenario_id == s.id))
    return _out(s, n or 0)


@router.get("/scenarios/{scenario_id}/test-cases")
async def scenario_test_cases(scenario_id: str, actor: CurrentActor, db: DbSession) -> dict:
    s = await db.get(Scenario, uuid.UUID(scenario_id))
    if s is None:
        raise ResourceNotFound("Scenario not found.")
    authz.require_member(actor, s.project_id)
    rows = (
        await db.scalars(
            select(TestCase)
            .where(TestCase.scenario_id == s.id)
            .order_by(*natural_key_order(TestCase))
        )
    ).all()
    return {
        "items": [
            {"id": str(t.id), "key": t.key, "title": t.title,
             "lifecycle_state": t.lifecycle_state, "automation_status": t.automation_status}
            for t in rows
        ]
    }


@router.patch("/scenarios/{scenario_id}")
async def update_scenario(scenario_id: str, body: UpdateScenario, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> dict:
    kwargs: dict = dict(
        scenario_id=uuid.UUID(scenario_id), expected_version=body.expected_version,
        title=body.title, description=body.description,
    )
    if body.clear_requirement:
        kwargs["requirement_id"] = None
    elif body.requirement_id is not None:
        kwargs["requirement_id"] = uuid.UUID(body.requirement_id)
    s = await scenarios.update_scenario(db, actor, ctx, **kwargs)
    return _out(s)


@router.post("/scenarios/{scenario_id}/status")
async def set_status(scenario_id: str, body: StatusRequest, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> dict:
    s = await scenarios.set_status(
        db, actor, ctx, scenario_id=uuid.UUID(scenario_id),
        expected_version=body.expected_version, status=body.status,
    )
    return _out(s)


@router.post("/scenarios/assign-test-case", status_code=200)
async def assign_test_case(body: AssignRequest, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> dict:
    tc = await scenarios.set_test_case_scenario(
        db, actor, ctx, test_case_id=uuid.UUID(body.test_case_id),
        scenario_id=uuid.UUID(body.scenario_id) if body.scenario_id else None,
    )
    return {"id": str(tc.id), "scenario_id": str(tc.scenario_id) if tc.scenario_id else None}
