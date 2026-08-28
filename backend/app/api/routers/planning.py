"""Plans, scope, cycles, cycle tests (increment 6)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentActor, DbSession, RequestCtx
from app.core.errors import ResourceNotFound
from app.domain import authz, planning
from app.domain.execution import resolve_cycle_test_result
from app.models import CycleTest, PlanScopeItem, TestCase, TestCycle, TestPlan

router = APIRouter(tags=["planning"])


class CreatePlan(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    objective: str | None = None
    release_id: str | None = None


class ScopeRequest(BaseModel):
    test_case_ids: list[str]


class CreateCycle(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    environment: str = "default"
    build: str = "unspecified"
    release_id: str | None = None
    description: str | None = None
    browser: str | None = None
    platform: str | None = None


class CycleScopeRequest(BaseModel):
    test_case_ids: list[str]
    assigned_to: str | None = None


class Transition(BaseModel):
    to: str
    expected_version: int
    reason: str | None = None


class PlanOut(BaseModel):
    id: str
    key: str
    name: str
    status: str
    release_id: str | None
    version: int


class CycleOut(BaseModel):
    id: str
    key: str
    plan_id: str
    name: str
    environment: str
    build: str
    release_id: str | None
    status: str
    version: int


def _plan_out(p: TestPlan) -> PlanOut:
    return PlanOut(id=str(p.id), key=p.key, name=p.name, status=p.status,
                   release_id=str(p.release_id) if p.release_id else None, version=p.version)


def _cycle_out(c: TestCycle) -> CycleOut:
    return CycleOut(id=str(c.id), key=c.key, plan_id=str(c.plan_id), name=c.name,
                    environment=c.environment, build=c.build,
                    release_id=str(c.release_id) if c.release_id else None,
                    status=c.status, version=c.version)


@router.post("/projects/{project_id}/plans", response_model=PlanOut, status_code=201)
async def create_plan(project_id: str, body: CreatePlan, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> PlanOut:
    p = await planning.create_plan(
        db, actor, ctx, project_id=uuid.UUID(project_id), name=body.name, description=body.description,
        objective=body.objective, release_id=uuid.UUID(body.release_id) if body.release_id else None,
    )
    return _plan_out(p)


@router.get("/projects/{project_id}/plans", response_model=list[PlanOut])
async def list_plans(project_id: str, actor: CurrentActor, db: DbSession) -> list[PlanOut]:
    pid = uuid.UUID(project_id)
    authz.require_member(actor, pid)
    rows = (await db.scalars(select(TestPlan).where(TestPlan.project_id == pid).order_by(TestPlan.key))).all()
    return [_plan_out(p) for p in rows]


@router.post("/plans/{plan_id}/scope", status_code=201)
async def add_scope(plan_id: str, body: ScopeRequest, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> dict:
    items = await planning.add_plan_scope(
        db, actor, ctx, plan_id=uuid.UUID(plan_id),
        test_case_ids=[uuid.UUID(x) for x in body.test_case_ids],
    )
    return {"added": len(items)}


@router.get("/plans/{plan_id}/scope")
async def list_scope(plan_id: str, actor: CurrentActor, db: DbSession) -> dict:
    plan = await db.get(TestPlan, uuid.UUID(plan_id))
    if plan is None:
        raise ResourceNotFound("Plan not found.")
    authz.require_member(actor, plan.project_id)
    rows = (await db.scalars(select(PlanScopeItem).where(PlanScopeItem.plan_id == plan.id))).all()
    return {"items": [{"test_case_id": str(r.test_case_id), "source": r.source} for r in rows]}


@router.post("/plans/{plan_id}/transitions", response_model=PlanOut)
async def transition_plan(plan_id: str, body: Transition, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> PlanOut:
    p = await planning.transition_plan(
        db, actor, ctx, plan_id=uuid.UUID(plan_id), to_status=body.to,
        expected_version=body.expected_version, reason=body.reason,
    )
    return _plan_out(p)


@router.post("/plans/{plan_id}/cycles", response_model=CycleOut, status_code=201)
async def create_cycle(plan_id: str, body: CreateCycle, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> CycleOut:
    c = await planning.create_cycle(
        db, actor, ctx, plan_id=uuid.UUID(plan_id), name=body.name, environment=body.environment,
        build=body.build, release_id=uuid.UUID(body.release_id) if body.release_id else None,
        description=body.description, browser=body.browser, platform=body.platform,
    )
    return _cycle_out(c)


@router.get("/projects/{project_id}/cycles", response_model=list[CycleOut])
async def list_cycles(project_id: str, actor: CurrentActor, db: DbSession) -> list[CycleOut]:
    pid = uuid.UUID(project_id)
    authz.require_member(actor, pid)
    rows = (await db.scalars(select(TestCycle).where(TestCycle.project_id == pid).order_by(TestCycle.key))).all()
    return [_cycle_out(c) for c in rows]


@router.post("/cycles/{cycle_id}/tests", status_code=201)
async def add_cycle_tests(cycle_id: str, body: CycleScopeRequest, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> dict:
    items = await planning.add_cycle_tests(
        db, actor, ctx, cycle_id=uuid.UUID(cycle_id),
        test_case_ids=[uuid.UUID(x) for x in body.test_case_ids],
        assigned_to=uuid.UUID(body.assigned_to) if body.assigned_to else None,
    )
    return {"added": len(items), "cycle_test_ids": [str(i.id) for i in items]}


@router.get("/cycles/{cycle_id}/tests")
async def list_cycle_tests(cycle_id: str, actor: CurrentActor, db: DbSession) -> dict:
    cycle = await db.get(TestCycle, uuid.UUID(cycle_id))
    if cycle is None:
        raise ResourceNotFound("Cycle not found.")
    authz.require_member(actor, cycle.project_id)
    rows = (
        await db.execute(
            select(CycleTest, TestCase.key, TestCase.title)
            .join(TestCase, TestCase.id == CycleTest.test_case_id)
            .where(CycleTest.cycle_id == cycle.id, CycleTest.removed_at.is_(None))
            .order_by(TestCase.key)
        )
    ).all()
    out = []
    for ct, tc_key, tc_title in rows:
        res = await resolve_cycle_test_result(db, ct.id)
        out.append({
            "id": str(ct.id),
            "test_case_id": str(ct.test_case_id),
            "test_case_key": tc_key,
            "test_case_title": tc_title,
            "test_case_version_id": str(ct.test_case_version_id) if ct.test_case_version_id else None,
            "assigned_to": str(ct.assigned_to) if ct.assigned_to else None,
            "displayed_result": res.displayed_result,
            "authoritative_attempt_id": str(res.authoritative_attempt_id) if res.authoritative_attempt_id else None,
            "in_progress_attempt_id": str(res.in_progress_attempt_id) if res.in_progress_attempt_id else None,
            "attempt_count": res.attempt_count,
        })
    return {"items": out}


@router.post("/cycles/{cycle_id}/transitions", response_model=CycleOut)
async def transition_cycle(cycle_id: str, body: Transition, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> CycleOut:
    c = await planning.transition_cycle(
        db, actor, ctx, cycle_id=uuid.UUID(cycle_id), to_status=body.to,
        expected_version=body.expected_version, reason=body.reason,
    )
    return _cycle_out(c)


@router.post("/cycle-tests/{cycle_test_id}/refresh-version")
async def refresh_version(cycle_test_id: str, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> dict:
    ct = await planning.refresh_cycle_test_version(db, actor, ctx, cycle_test_id=uuid.UUID(cycle_test_id))
    return {"id": str(ct.id), "test_case_version_id": str(ct.test_case_version_id)}


@router.delete("/cycle-tests/{cycle_test_id}", status_code=204)
async def remove_cycle_test(cycle_test_id: str, actor: CurrentActor, db: DbSession, ctx: RequestCtx):
    await planning.remove_cycle_test(db, actor, ctx, cycle_test_id=uuid.UUID(cycle_test_id))
