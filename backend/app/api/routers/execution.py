"""Manual execution (increment 7)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentActor, DbSession, RequestCtx
from app.core.errors import ResourceNotFound
from app.domain import authz, execution
from app.models import ExecutionAttempt, ExecutionCorrection, ExecutionStep

router = APIRouter(tags=["execution"])


class StepResultRequest(BaseModel):
    result: str
    comment: str | None = None


class CompleteRequest(BaseModel):
    override_result: str | None = None
    override_reason: str | None = None
    notes: str | None = None


class AbortRequest(BaseModel):
    reason: str = Field(min_length=1)


class CorrectionRequest(BaseModel):
    field: str = "overall_result"
    new_value: str
    reason: str = Field(min_length=1)


class DefectLinkRequest(BaseModel):
    defect_id: str


class StepOut(BaseModel):
    order_index: int
    action: str
    expected_result: str
    is_required: bool
    result: str
    comment: str | None


class AttemptOut(BaseModel):
    id: str
    cycle_test_id: str
    status: str
    overall_result: str | None
    result_overridden: bool
    environment: str
    build: str
    started_at: str
    ended_at: str | None
    steps: list[StepOut]
    corrections: list[dict]


async def _attempt_out(db, attempt: ExecutionAttempt) -> AttemptOut:
    steps = (
        await db.scalars(
            select(ExecutionStep).where(ExecutionStep.attempt_id == attempt.id).order_by(ExecutionStep.order_index)
        )
    ).all()
    corrections = (
        await db.scalars(
            select(ExecutionCorrection).where(ExecutionCorrection.attempt_id == attempt.id).order_by(ExecutionCorrection.created_at)
        )
    ).all()
    return AttemptOut(
        id=str(attempt.id),
        cycle_test_id=str(attempt.cycle_test_id),
        status=attempt.status,
        overall_result=attempt.overall_result,
        result_overridden=attempt.result_overridden,
        environment=attempt.environment,
        build=attempt.build,
        started_at=attempt.started_at.isoformat(),
        ended_at=attempt.ended_at.isoformat() if attempt.ended_at else None,
        steps=[
            StepOut(order_index=s.order_index, action=s.action, expected_result=s.expected_result,
                    is_required=s.is_required, result=s.result, comment=s.comment)
            for s in steps
        ],
        corrections=[
            {"field": c.field, "old_value": c.old_value, "new_value": c.new_value, "reason": c.reason,
             "created_at": c.created_at.isoformat()}
            for c in corrections
        ],
    )


@router.post("/cycle-tests/{cycle_test_id}/attempts", response_model=AttemptOut, status_code=201)
async def start_attempt(cycle_test_id: str, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> AttemptOut:
    a = await execution.start_attempt(db, actor, ctx, cycle_test_id=uuid.UUID(cycle_test_id))
    return await _attempt_out(db, a)


@router.post("/cycle-tests/{cycle_test_id}/retest")
async def request_retest(cycle_test_id: str, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> dict:
    ct = await execution.request_retest(db, actor, ctx, cycle_test_id=uuid.UUID(cycle_test_id))
    return {"id": str(ct.id), "retest_requested": True}


@router.get("/attempts/{attempt_id}", response_model=AttemptOut)
async def get_attempt(attempt_id: str, actor: CurrentActor, db: DbSession) -> AttemptOut:
    a = await db.get(ExecutionAttempt, uuid.UUID(attempt_id))
    if a is None:
        raise ResourceNotFound("Attempt not found.")
    authz.require_member(actor, a.project_id)
    return await _attempt_out(db, a)


@router.patch("/attempts/{attempt_id}/steps/{order_index}", response_model=AttemptOut)
async def set_step(
    attempt_id: str, order_index: int, body: StepResultRequest,
    actor: CurrentActor, db: DbSession, ctx: RequestCtx,
) -> AttemptOut:
    a = await execution.set_step_result(
        db, actor, ctx, attempt_id=uuid.UUID(attempt_id), order_index=order_index,
        result=body.result, comment=body.comment,
    )
    return await _attempt_out(db, a)


@router.post("/attempts/{attempt_id}/complete", response_model=AttemptOut)
async def complete(attempt_id: str, body: CompleteRequest, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> AttemptOut:
    a = await execution.complete_attempt(
        db, actor, ctx, attempt_id=uuid.UUID(attempt_id), override_result=body.override_result,
        override_reason=body.override_reason, notes=body.notes,
    )
    return await _attempt_out(db, a)


@router.post("/attempts/{attempt_id}/abort", response_model=AttemptOut)
async def abort(attempt_id: str, body: AbortRequest, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> AttemptOut:
    a = await execution.abort_attempt(db, actor, ctx, attempt_id=uuid.UUID(attempt_id), reason=body.reason)
    return await _attempt_out(db, a)


@router.post("/attempts/{attempt_id}/corrections", response_model=AttemptOut, status_code=201)
async def correct(attempt_id: str, body: CorrectionRequest, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> AttemptOut:
    a = await execution.correct_attempt(
        db, actor, ctx, attempt_id=uuid.UUID(attempt_id), field=body.field,
        new_value=body.new_value, reason=body.reason,
    )
    return await _attempt_out(db, a)


@router.post("/attempts/{attempt_id}/defects", status_code=201)
async def link_defect(attempt_id: str, body: DefectLinkRequest, actor: CurrentActor, db: DbSession, ctx: RequestCtx) -> dict:
    link = await execution.link_defect(
        db, actor, ctx, attempt_id=uuid.UUID(attempt_id), defect_id=uuid.UUID(body.defect_id)
    )
    return {"attempt_id": str(link.attempt_id), "defect_id": str(link.defect_id)}
