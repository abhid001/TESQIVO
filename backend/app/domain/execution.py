"""Manual execution: attempts, step results, result derivation, retest,
corrections, and authoritative-attempt resolution (increment 7, PRS §7.3-§7.5).

Completed attempts are immutable. A manager correction is an append-only
execution_correction row; the original attempt evidence is never rewritten.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import Actor, Ctx
from app.core.errors import (
    ResourceNotFound,
    StateTransitionNotAllowed,
    ValidationFailed,
)
from app.domain import audit, authz
from app.models import (
    AttemptDefectLink,
    CycleTest,
    CycleTestStep,
    Defect,
    ExecutionAttempt,
    ExecutionCorrection,
    ExecutionStep,
    TestCycle,
)

TERMINAL = ("PASSED", "FAILED", "BLOCKED", "SKIPPED", "ABORTED")
PASSING = ("PASSED",)
STEP_RESULTS = ("not_run", "passed", "failed", "blocked", "skipped")


def _now() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- derivation


def derive_overall_result(steps: list[ExecutionStep]) -> str:
    """Pure function (PRS §7.4)."""
    required = [s for s in steps if s.is_required]
    if any(s.result == "not_run" for s in required):
        return "IN_PROGRESS"
    if any(s.result == "failed" for s in required):
        return "FAILED"
    if any(s.result == "blocked" for s in required):
        return "BLOCKED"
    if all(s.result in ("passed", "skipped") for s in required):
        return "PASSED"
    return "IN_PROGRESS"


# --------------------------------------------------------------------------- attempts


async def start_attempt(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, cycle_test_id: uuid.UUID
) -> ExecutionAttempt:
    ct = await _get_cycle_test(session, cycle_test_id)
    authz.authorize(actor, "cycle_test.execute", project_id=ct.project_id, resource=ct)
    cycle = await session.get(TestCycle, ct.cycle_id)
    assert cycle is not None
    if cycle.status not in ("active", "reopened"):
        raise StateTransitionNotAllowed("The cycle is not active.")
    if ct.test_case_version_id is None:
        raise ValidationFailed("This cycle test has no version snapshot; activate the cycle first.")
    open_attempt = await session.scalar(
        select(ExecutionAttempt).where(
            ExecutionAttempt.cycle_test_id == cycle_test_id,
            ExecutionAttempt.status == "IN_PROGRESS",
        )
    )
    if open_attempt is not None:
        raise StateTransitionNotAllowed("An attempt is already in progress for this cycle test.")

    attempt = ExecutionAttempt(
        cycle_test_id=cycle_test_id,
        project_id=ct.project_id,
        plan_id=cycle.plan_id,
        cycle_id=ct.cycle_id,
        test_case_version_id=ct.test_case_version_id,
        release_id=cycle.release_id,
        environment=cycle.environment,
        build=cycle.build,
        tester_id=actor.id,
        status="IN_PROGRESS",
    )
    session.add(attempt)
    await session.flush()
    snap_steps = list(
        await session.scalars(
            select(CycleTestStep)
            .where(CycleTestStep.cycle_test_id == cycle_test_id)
            .order_by(CycleTestStep.order_index)
        )
    )
    for s in snap_steps:
        session.add(
            ExecutionStep(
                attempt_id=attempt.id,
                cycle_test_step_id=s.id,
                order_index=s.order_index,
                action=s.action,
                expected_result=s.expected_result,
                is_required=s.is_required,
                result="not_run",
            )
        )
    ct.retest_requested_at = None
    await session.flush()
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="execution_attempt", action="attempt.started",
        entity_id=attempt.id, project_id=ct.project_id,
    )
    await session.commit()
    return attempt


async def set_step_result(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    attempt_id: uuid.UUID,
    order_index: int,
    result: str,
    comment: str | None = None,
) -> ExecutionAttempt:
    attempt = await _get_attempt(session, attempt_id)
    ct = await _get_cycle_test(session, attempt.cycle_test_id)
    authz.authorize(actor, "cycle_test.execute", project_id=attempt.project_id, resource=ct)
    if attempt.status != "IN_PROGRESS":
        raise StateTransitionNotAllowed("This attempt is complete and cannot be edited.")
    if result not in STEP_RESULTS:
        raise ValidationFailed(f"Invalid step result '{result}'.")
    step = await session.scalar(
        select(ExecutionStep).where(
            ExecutionStep.attempt_id == attempt_id, ExecutionStep.order_index == order_index
        )
    )
    if step is None:
        raise ResourceNotFound("Step not found.")
    step.result = result
    step.comment = comment
    step.recorded_at = _now()
    await session.flush()
    await session.commit()
    return attempt


async def complete_attempt(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    attempt_id: uuid.UUID,
    override_result: str | None = None,
    override_reason: str | None = None,
    notes: str | None = None,
) -> ExecutionAttempt:
    attempt = await _get_attempt(session, attempt_id)
    ct = await _get_cycle_test(session, attempt.cycle_test_id)
    authz.authorize(actor, "cycle_test.execute", project_id=attempt.project_id, resource=ct)
    if attempt.status != "IN_PROGRESS":
        raise StateTransitionNotAllowed("This attempt is already complete.")

    steps = list(await session.scalars(select(ExecutionStep).where(ExecutionStep.attempt_id == attempt_id)))
    derived = derive_overall_result(steps)

    if override_result is not None:
        if override_result not in TERMINAL:
            raise ValidationFailed(f"Invalid overall result '{override_result}'.")
        if not override_reason:
            raise ValidationFailed("An override requires an audited reason.")
        authz.authorize(actor, "attempt.correct", project_id=attempt.project_id)
        final = override_result
        attempt.result_overridden = True
        attempt.override_reason = override_reason
    else:
        if derived == "IN_PROGRESS":
            raise ValidationFailed(
                "Every required step needs a result before completing (or provide an override)."
            )
        final = derived

    attempt.status = final
    attempt.overall_result = final
    attempt.ended_at = _now()
    attempt.duration_seconds = int((attempt.ended_at - attempt.started_at).total_seconds())
    if notes:
        attempt.notes = notes
    await session.flush()
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="execution_attempt", action="attempt.completed",
        entity_id=attempt.id, project_id=attempt.project_id,
        after={"result": final, "overridden": attempt.result_overridden},
    )
    await session.commit()
    return attempt


async def abort_attempt(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, attempt_id: uuid.UUID, reason: str
) -> ExecutionAttempt:
    attempt = await _get_attempt(session, attempt_id)
    ct = await _get_cycle_test(session, attempt.cycle_test_id)
    authz.authorize(actor, "cycle_test.execute", project_id=attempt.project_id, resource=ct)
    if attempt.status != "IN_PROGRESS":
        raise StateTransitionNotAllowed("This attempt is already complete.")
    if not reason:
        raise ValidationFailed("A reason is required to abort an attempt.")
    attempt.status = "ABORTED"
    attempt.overall_result = "ABORTED"
    attempt.ended_at = _now()
    attempt.notes = (attempt.notes or "") + f"\n[aborted] {reason}"
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="execution_attempt", action="attempt.aborted",
        entity_id=attempt.id, project_id=attempt.project_id, after={"reason": reason},
    )
    await session.commit()
    return attempt


async def request_retest(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, cycle_test_id: uuid.UUID
) -> CycleTest:
    ct = await _get_cycle_test(session, cycle_test_id)
    authz.authorize(actor, "cycle_test.execute", project_id=ct.project_id, resource=ct)
    completed = await session.scalar(
        select(func.count()).select_from(ExecutionAttempt).where(
            ExecutionAttempt.cycle_test_id == cycle_test_id,
            ExecutionAttempt.status.in_(TERMINAL),
        )
    )
    if not completed:
        raise StateTransitionNotAllowed("There is no completed attempt to retest.")
    ct.retest_requested_at = _now()
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="cycle_test", action="cycle_test.retest_requested",
        entity_id=ct.id, project_id=ct.project_id,
    )
    await session.commit()
    return ct


async def correct_attempt(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    attempt_id: uuid.UUID,
    field: str,
    new_value: str,
    reason: str,
) -> ExecutionAttempt:
    attempt = await _get_attempt(session, attempt_id)
    authz.authorize(actor, "attempt.correct", project_id=attempt.project_id)
    if attempt.status not in TERMINAL:
        raise StateTransitionNotAllowed("Only completed attempts can be corrected.")
    if field != "overall_result":
        raise ValidationFailed("Phase 1 supports correcting 'overall_result' only.")
    if new_value not in TERMINAL:
        raise ValidationFailed(f"Invalid overall result '{new_value}'.")
    if not reason:
        raise ValidationFailed("A correction requires a reason.")
    old = attempt.overall_result
    session.add(
        ExecutionCorrection(
            attempt_id=attempt_id,
            field=field,
            old_value=old,
            new_value=new_value,
            actor_id=actor.id,
            reason=reason,
        )
    )
    # NOTE: the attempt row's evidence is NOT rewritten. Reporting reads the latest
    # correction via the authoritative-attempt resolver.
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="execution_attempt", action="attempt.corrected",
        entity_id=attempt_id, project_id=attempt.project_id,
        before={"overall_result": old}, after={"overall_result": new_value, "reason": reason},
    )
    await session.commit()
    return attempt


async def link_defect(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, attempt_id: uuid.UUID, defect_id: uuid.UUID
) -> AttemptDefectLink:
    attempt = await _get_attempt(session, attempt_id)
    authz.authorize(actor, "defect.manage", project_id=attempt.project_id)
    defect = await session.get(Defect, defect_id)
    if defect is None or defect.project_id != attempt.project_id:
        raise ValidationFailed("Defect not found in this project.")
    dupe = await session.scalar(
        select(AttemptDefectLink).where(
            AttemptDefectLink.attempt_id == attempt_id, AttemptDefectLink.defect_id == defect_id
        )
    )
    if dupe is not None:
        return dupe
    link = AttemptDefectLink(attempt_id=attempt_id, defect_id=defect_id, created_by=actor.id)
    session.add(link)
    await session.flush()
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="execution_attempt", action="attempt.defect_linked",
        entity_id=attempt_id, project_id=attempt.project_id, after={"defect_id": str(defect_id)},
    )
    await session.commit()
    return link


# --------------------------------------------------------------------------- read models


@dataclass
class CycleTestResult:
    cycle_test_id: uuid.UUID
    displayed_result: str
    authoritative_attempt_id: uuid.UUID | None
    in_progress_attempt_id: uuid.UUID | None
    attempt_count: int


async def resolve_cycle_test_result(
    session: AsyncSession, cycle_test_id: uuid.UUID
) -> CycleTestResult:
    ct = await _get_cycle_test(session, cycle_test_id)
    attempts = list(
        await session.scalars(
            select(ExecutionAttempt).where(ExecutionAttempt.cycle_test_id == cycle_test_id)
        )
    )
    in_progress = next((a for a in attempts if a.status == "IN_PROGRESS"), None)
    completed = [a for a in attempts if a.status in TERMINAL]
    if not completed:
        displayed = "RETEST_PENDING" if ct.retest_requested_at else "NOT_RUN"
        return CycleTestResult(cycle_test_id, displayed, None, in_progress.id if in_progress else None, len(attempts))

    # authoritative-attempt sort (PRS §7.5)
    async def sort_key(a: ExecutionAttempt):
        latest_corr = await session.scalar(
            select(func.max(ExecutionCorrection.created_at)).where(
                ExecutionCorrection.attempt_id == a.id,
                ExecutionCorrection.field == "overall_result",
            )
        )
        return (latest_corr or a.ended_at, a.ended_at, str(a.id))

    keyed = sorted(
        [(await sort_key(a), a) for a in completed], key=lambda t: t[0]
    )
    authoritative = keyed[-1][1]
    latest_corr_value = await session.scalar(
        select(ExecutionCorrection.new_value)
        .where(
            ExecutionCorrection.attempt_id == authoritative.id,
            ExecutionCorrection.field == "overall_result",
        )
        .order_by(ExecutionCorrection.created_at.desc())
        .limit(1)
    )
    effective = latest_corr_value or authoritative.overall_result or "NOT_RUN"
    displayed = "RETEST_PENDING" if ct.retest_requested_at and not in_progress else effective
    return CycleTestResult(
        cycle_test_id,
        displayed,
        authoritative.id,
        in_progress.id if in_progress else None,
        len(attempts),
    )


async def _get_attempt(session: AsyncSession, attempt_id: uuid.UUID) -> ExecutionAttempt:
    a = await session.get(ExecutionAttempt, attempt_id)
    if a is None:
        raise ResourceNotFound("Attempt not found.")
    return a


async def _get_cycle_test(session: AsyncSession, cycle_test_id: uuid.UUID) -> CycleTest:
    ct = await session.get(CycleTest, cycle_test_id)
    if ct is None:
        raise ResourceNotFound("Cycle test not found.")
    return ct
