"""Test plans, scope, cycles, cycle tests, and activation snapshot (increment 6).

Cycle activation copies the approved version's steps into each Cycle Test. Later
edits / moves / deprecation / archival of the source Test Case never mutate the
snapshot (PRS §7.2).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import Actor, Ctx
from app.core.errors import (
    DuplicateResource,
    ResourceNotFound,
    StateTransitionNotAllowed,
    ValidationFailed,
)
from app.domain import audit, authz
from app.domain.concurrency import check_version
from app.domain.keys import next_key
from app.models import (
    CycleTest,
    CycleTestStep,
    ExecutionAttempt,
    PlanScopeItem,
    Project,
    Release,
    TestCase,
    TestCaseVersion,
    TestCycle,
    TestPlan,
    TestStep,
)


def _now() -> datetime:
    return datetime.now(UTC)


async def _project(session: AsyncSession, project_id: uuid.UUID) -> Project:
    p = await session.get(Project, project_id)
    if p is None:
        raise ResourceNotFound("Project not found.")
    return p


# --------------------------------------------------------------------------- plans


async def create_plan(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    project_id: uuid.UUID,
    name: str,
    description: str | None = None,
    objective: str | None = None,
    release_id: uuid.UUID | None = None,
) -> TestPlan:
    await _project(session, project_id)
    authz.authorize(actor, "plan.manage", project_id=project_id)
    await _validate_same_project_release(session, project_id, release_id)
    plan = TestPlan(
        project_id=project_id,
        key=await next_key(session, project_id, "test_plan"),
        name=name.strip(),
        description=description,
        objective=objective,
        owner_id=actor.id,
        release_id=release_id,
        status="draft",
        created_by=actor.id,
    )
    session.add(plan)
    await session.flush()
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="test_plan", action="plan.created",
        entity_id=plan.id, entity_key=plan.key, project_id=project_id, after={"name": plan.name},
    )
    await session.commit()
    return plan


async def add_plan_scope(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    plan_id: uuid.UUID,
    test_case_ids: list[uuid.UUID],
) -> list[PlanScopeItem]:
    plan = await _get_plan(session, plan_id)
    authz.authorize(actor, "plan.manage", project_id=plan.project_id)
    if plan.status not in ("draft", "active"):
        raise StateTransitionNotAllowed("Scope can only be changed on Draft or Active plans.")
    added: list[PlanScopeItem] = []
    for tc_id in test_case_ids:
        tc = await session.get(TestCase, tc_id)
        if tc is None or tc.project_id != plan.project_id:
            raise ValidationFailed(f"Test case {tc_id} not found in this project.")
        exists = await session.scalar(
            select(PlanScopeItem).where(
                PlanScopeItem.plan_id == plan_id, PlanScopeItem.test_case_id == tc_id
            )
        )
        if exists is not None:
            continue  # a plan may contain a test case at most once (PRS §7.1)
        item = PlanScopeItem(plan_id=plan_id, test_case_id=tc_id, added_by=actor.id, source="manual")
        session.add(item)
        added.append(item)
    await session.flush()
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="test_plan", action="plan.scope_added",
        entity_id=plan.id, entity_key=plan.key, project_id=plan.project_id,
        after={"count": len(added)},
    )
    await session.commit()
    return added


async def transition_plan(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    plan_id: uuid.UUID,
    to_status: str,
    expected_version: int,
    reason: str | None = None,
) -> TestPlan:
    plan = await _get_plan(session, plan_id)
    action = "plan.reopen" if (plan.status == "completed" and to_status == "active") else "plan.manage"
    authz.authorize(actor, action, project_id=plan.project_id)
    check_version(plan.version, expected_version, entity="plan")
    allowed = {
        ("draft", "active"), ("active", "completed"), ("completed", "active"),
        ("draft", "archived"), ("active", "archived"), ("completed", "archived"),
    }
    if (plan.status, to_status) not in allowed:
        raise StateTransitionNotAllowed(f"Cannot move plan from '{plan.status}' to '{to_status}'.")
    if to_status == "active" and plan.status == "draft":
        has_scope = await session.scalar(
            select(func.count()).select_from(PlanScopeItem).where(PlanScopeItem.plan_id == plan_id)
        )
        has_cycle = await session.scalar(
            select(func.count()).select_from(TestCycle).where(TestCycle.plan_id == plan_id)
        )
        if not (has_scope or has_cycle):
            raise StateTransitionNotAllowed(
                "A Draft plan needs at least one cycle or scoped test before activation."
            )
    if plan.status == "completed" and to_status == "active" and not reason:
        raise ValidationFailed("A reason is required to reopen a completed plan.")
    before = plan.status
    plan.status = to_status
    plan.version += 1
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="test_plan",
        action=f"plan.{to_status}", entity_id=plan.id, entity_key=plan.key,
        project_id=plan.project_id, before={"status": before},
        after={"status": to_status, "reason": reason},
    )
    await session.commit()
    return plan


# --------------------------------------------------------------------------- cycles


async def create_cycle(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    plan_id: uuid.UUID,
    name: str,
    environment: str,
    build: str,
    release_id: uuid.UUID | None = None,
    description: str | None = None,
    browser: str | None = None,
    platform: str | None = None,
) -> TestCycle:
    plan = await _get_plan(session, plan_id)
    authz.authorize(actor, "cycle.manage", project_id=plan.project_id)
    await _validate_same_project_release(session, plan.project_id, release_id)
    cycle = TestCycle(
        plan_id=plan_id,
        project_id=plan.project_id,
        key=await next_key(session, plan.project_id, "test_cycle"),
        name=name.strip(),
        description=description,
        release_id=release_id or plan.release_id,
        environment=environment.strip() or "default",
        build=build.strip() or "unspecified",
        browser=browser,
        platform=platform,
        status="draft",
        created_by=actor.id,
    )
    session.add(cycle)
    await session.flush()
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="test_cycle", action="cycle.created",
        entity_id=cycle.id, entity_key=cycle.key, project_id=plan.project_id, after={"name": cycle.name},
    )
    await session.commit()
    return cycle


async def add_cycle_tests(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    cycle_id: uuid.UUID,
    test_case_ids: list[uuid.UUID],
    assigned_to: uuid.UUID | None = None,
) -> list[CycleTest]:
    cycle = await _get_cycle(session, cycle_id)
    authz.authorize(actor, "cycle.manage", project_id=cycle.project_id)
    if cycle.status not in ("draft", "active", "reopened"):
        raise StateTransitionNotAllowed("Cannot change scope of a completed/archived cycle.")
    added: list[CycleTest] = []
    for tc_id in test_case_ids:
        tc = await session.get(TestCase, tc_id)
        if tc is None or tc.project_id != cycle.project_id:
            raise ValidationFailed(f"Test case {tc_id} not found in this project.")
        dupe = await session.scalar(
            select(CycleTest).where(
                CycleTest.cycle_id == cycle_id,
                CycleTest.test_case_id == tc_id,
                CycleTest.removed_at.is_(None),
            )
        )
        if dupe is not None:
            raise DuplicateResource(
                f"{tc.key} is already in this cycle. Use a separate cycle for another environment/build."
            )
        ct = CycleTest(
            cycle_id=cycle_id,
            project_id=cycle.project_id,
            test_case_id=tc_id,
            assigned_to=assigned_to,
            added_by=actor.id,
        )
        # If the cycle is already active, snapshot immediately.
        if cycle.status in ("active", "reopened"):
            await _snapshot_cycle_test(session, ct, tc)
        session.add(ct)
        added.append(ct)
    await session.flush()
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="test_cycle", action="cycle.scope_added",
        entity_id=cycle.id, entity_key=cycle.key, project_id=cycle.project_id, after={"count": len(added)},
    )
    await session.commit()
    return added


async def transition_cycle(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    cycle_id: uuid.UUID,
    to_status: str,
    expected_version: int,
    reason: str | None = None,
) -> TestCycle:
    cycle = await _get_cycle(session, cycle_id)
    reopening = cycle.status == "completed" and to_status == "reopened"
    authz.authorize(actor, "cycle.reopen" if reopening else "cycle.manage", project_id=cycle.project_id)
    check_version(cycle.version, expected_version, entity="cycle")
    allowed = {
        ("draft", "active"), ("active", "completed"), ("completed", "reopened"),
        ("reopened", "completed"), ("draft", "archived"), ("active", "archived"),
        ("completed", "archived"), ("reopened", "archived"),
    }
    if (cycle.status, to_status) not in allowed:
        raise StateTransitionNotAllowed(f"Cannot move cycle from '{cycle.status}' to '{to_status}'.")

    cycle_tests = list(
        await session.scalars(
            select(CycleTest).where(CycleTest.cycle_id == cycle_id, CycleTest.removed_at.is_(None))
        )
    )

    if to_status == "active" and cycle.status == "draft":
        if not cycle_tests:
            raise StateTransitionNotAllowed("Activation requires at least one Cycle Test.")
        missing: list[str] = []
        for ct in cycle_tests:
            tc = await session.get(TestCase, ct.test_case_id)
            assert tc is not None
            if tc.approved_version_id is None:
                missing.append(tc.key)
            else:
                await _snapshot_cycle_test(session, ct, tc)
        if missing:
            raise ValidationFailed(
                "Some test cases have no approved version.",
                details=[{"field": "/cycle_tests", "code": "MISSING_APPROVED_VERSION", "message": k} for k in missing],
            )

    if to_status == "completed":
        in_progress = await session.scalar(
            select(func.count())
            .select_from(ExecutionAttempt)
            .where(ExecutionAttempt.cycle_id == cycle_id, ExecutionAttempt.status == "IN_PROGRESS")
        )
        if in_progress:
            raise StateTransitionNotAllowed("Complete or abort in-progress attempts first.")

    if reopening and not reason:
        raise ValidationFailed("A reason is required to reopen a completed cycle.")

    before = cycle.status
    cycle.status = to_status
    cycle.version += 1
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="test_cycle", action=f"cycle.{to_status}",
        entity_id=cycle.id, entity_key=cycle.key, project_id=cycle.project_id,
        before={"status": before}, after={"status": to_status, "reason": reason},
    )
    await session.commit()
    return cycle


async def refresh_cycle_test_version(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, cycle_test_id: uuid.UUID
) -> CycleTest:
    ct = await session.get(CycleTest, cycle_test_id)
    if ct is None:
        raise ResourceNotFound("Cycle test not found.")
    authz.authorize(actor, "cycle.manage", project_id=ct.project_id)
    has_attempt = await session.scalar(
        select(func.count()).select_from(ExecutionAttempt).where(
            ExecutionAttempt.cycle_test_id == cycle_test_id
        )
    )
    if has_attempt:
        raise StateTransitionNotAllowed(
            "A cycle test with an attempt cannot be silently refreshed (PRS §7.2)."
        )
    tc = await session.get(TestCase, ct.test_case_id)
    assert tc is not None
    if tc.approved_version_id is None:
        raise ValidationFailed("The test case has no approved version to refresh to.")
    await _snapshot_cycle_test(session, ct, tc)
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="cycle_test", action="cycle_test.version_refreshed",
        entity_id=ct.id, project_id=ct.project_id, after={"version_id": str(tc.approved_version_id)},
    )
    await session.commit()
    return ct


async def _snapshot_cycle_test(session: AsyncSession, ct: CycleTest, tc: TestCase) -> None:
    version = await session.get(TestCaseVersion, tc.approved_version_id)
    assert version is not None
    ct.test_case_version_id = version.id
    ct.snapshot_taken_at = _now()
    await session.execute(
        CycleTestStep.__table__.delete().where(CycleTestStep.cycle_test_id == ct.id)
    )
    steps = list(
        await session.scalars(
            select(TestStep).where(TestStep.version_id == version.id).order_by(TestStep.order_index)
        )
    )
    for s in steps:
        session.add(
            CycleTestStep(
                cycle_test_id=ct.id,
                order_index=s.order_index,
                action=s.action,
                expected_result=s.expected_result,
                is_required=s.is_required,
            )
        )
    await session.flush()


async def _validate_same_project_release(
    session: AsyncSession, project_id: uuid.UUID, release_id: uuid.UUID | None
) -> None:
    if release_id is None:
        return
    rel = await session.get(Release, release_id)
    if rel is None or rel.project_id != project_id:
        raise ValidationFailed("Release not found in this project (cross-project links are rejected).")


async def _get_plan(session: AsyncSession, plan_id: uuid.UUID) -> TestPlan:
    plan = await session.get(TestPlan, plan_id)
    if plan is None:
        raise ResourceNotFound("Plan not found.")
    return plan


async def _get_cycle(session: AsyncSession, cycle_id: uuid.UUID) -> TestCycle:
    cycle = await session.get(TestCycle, cycle_id)
    if cycle is None:
        raise ResourceNotFound("Cycle not found.")
    return cycle
