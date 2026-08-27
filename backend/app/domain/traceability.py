"""Trace links and the traceability matrix (increment 8, PRS §8.2).

Links are first-class, soft-removable records. Only the 9 Phase 1 relationship
types are legal. All endpoints must share a project (cross-project links rejected).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import Actor, Ctx
from app.core.errors import DuplicateResource, ResourceNotFound, ValidationFailed
from app.domain import audit, authz
from app.models import (
    CycleTest,
    Defect,
    ExecutionAttempt,
    Release,
    Requirement,
    TestCase,
    TestCaseVersion,
    TestCycle,
    TestPlan,
    TraceLink,
)

# (source_type, target_type) -> relationship_type
LEGAL_RELATIONSHIPS: dict[tuple[str, str], str] = {
    ("requirement", "test_case"): "covers",
    ("requirement", "release"): "targets",
    ("release", "test_plan"): "scopes",
    ("release", "test_cycle"): "scopes",
    ("test_case_version", "cycle_test"): "planned_as",
    ("cycle_test", "execution_attempt"): "executed_by",
    ("execution_attempt", "defect"): "raised",
    ("defect", "requirement"): "regresses",
    ("defect", "release"): "affects",
}

_MODEL_BY_TYPE = {
    "requirement": Requirement,
    "release": Release,
    "test_plan": TestPlan,
    "test_cycle": TestCycle,
    "test_case": TestCase,
    "test_case_version": TestCaseVersion,
    "cycle_test": CycleTest,
    "execution_attempt": ExecutionAttempt,
    "defect": Defect,
}


async def _entity_project(session: AsyncSession, etype: str, eid: uuid.UUID) -> uuid.UUID | None:
    model = _MODEL_BY_TYPE.get(etype)
    if model is None:
        return None
    obj = await session.get(model, eid)
    if obj is None:
        return None
    if etype == "test_case_version":
        tc = await session.get(TestCase, obj.test_case_id)
        return tc.project_id if tc else None
    return getattr(obj, "project_id", None)


async def create_link(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    project_id: uuid.UUID,
    source_type: str,
    source_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
    origin: str = "manual",
    external_reference: str | None = None,
) -> TraceLink:
    authz.authorize(actor, "trace_link.manage", project_id=project_id)
    rel = LEGAL_RELATIONSHIPS.get((source_type, target_type))
    if rel is None:
        raise ValidationFailed(
            f"Relationship {source_type} -> {target_type} is not allowed in Phase 1.",
            details=[{"field": "/relationship", "code": "RELATIONSHIP_NOT_ALLOWED", "message": "Not allowed."}],
        )
    for etype, eid in ((source_type, source_id), (target_type, target_id)):
        ep = await _entity_project(session, etype, eid)
        if ep is None:
            raise ValidationFailed(f"{etype} {eid} not found.")
        if ep != project_id:
            raise ValidationFailed("Cross-project links are rejected in Phase 1.")

    dupe = await session.scalar(
        select(TraceLink).where(
            TraceLink.source_type == source_type,
            TraceLink.source_id == source_id,
            TraceLink.target_type == target_type,
            TraceLink.target_id == target_id,
            TraceLink.relationship_type == rel,
            TraceLink.removed_at.is_(None),
        )
    )
    if dupe is not None:
        raise DuplicateResource("That link already exists.")

    link = TraceLink(
        project_id=project_id,
        source_type=source_type,
        source_id=source_id,
        target_type=target_type,
        target_id=target_id,
        relationship_type=rel,
        origin=origin,
        created_by=actor.id,
        external_reference=external_reference,
    )
    session.add(link)
    await session.flush()
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="trace_link", action="link.created",
        entity_id=link.id, project_id=project_id,
        after={"rel": rel, "source": f"{source_type}:{source_id}", "target": f"{target_type}:{target_id}"},
    )
    await session.commit()
    return link


async def remove_link(session: AsyncSession, actor: Actor, ctx: Ctx, *, link_id: uuid.UUID) -> None:
    link = await session.get(TraceLink, link_id)
    if link is None or link.removed_at is not None:
        raise ResourceNotFound("Link not found.")
    authz.authorize(actor, "trace_link.manage", project_id=link.project_id, resource=link)
    from datetime import UTC, datetime

    link.removed_at = datetime.now(UTC)
    link.removed_by = actor.id
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="trace_link", action="link.removed",
        entity_id=link.id, project_id=link.project_id,
    )
    await session.commit()


async def list_links(
    session: AsyncSession,
    actor: Actor,
    *,
    project_id: uuid.UUID,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    include_removed: bool = False,
) -> list[TraceLink]:
    authz.require_member(actor, project_id)
    stmt = select(TraceLink).where(TraceLink.project_id == project_id)
    if not include_removed:
        stmt = stmt.where(TraceLink.removed_at.is_(None))
    if entity_type and entity_id:
        stmt = stmt.where(
            or_(
                and_(TraceLink.source_type == entity_type, TraceLink.source_id == entity_id),
                and_(TraceLink.target_type == entity_type, TraceLink.target_id == entity_id),
            )
        )
    return list((await session.scalars(stmt.order_by(TraceLink.created_at))).all())


# --------------------------------------------------------------------------- matrix


@dataclass
class MatrixRow:
    requirement_id: uuid.UUID
    requirement_key: str
    requirement_title: str
    requirement_status: str
    linked_test_case_keys: list[str]
    planned_version_labels: list[str]
    latest_results: list[str]
    open_critical_defects: int


async def build_matrix(
    session: AsyncSession,
    actor: Actor,
    *,
    project_id: uuid.UUID,
    release_id: uuid.UUID | None = None,
    cycle_id: uuid.UUID | None = None,
) -> list[MatrixRow]:
    """Requirement-centric matrix. Resolves Requirement->Test Case links to the
    version a relevant Cycle Test snapshotted (PRS §8.2)."""
    from app.domain.execution import resolve_cycle_test_result

    authz.require_member(actor, project_id)
    reqs = list(
        await session.scalars(
            select(Requirement)
            .where(Requirement.project_id == project_id, Requirement.status != "archived")
            .order_by(Requirement.key)
        )
    )
    rows: list[MatrixRow] = []
    for req in reqs:
        tc_links = await list_links(
            session, actor, project_id=project_id, entity_type="requirement", entity_id=req.id
        )
        tc_ids = [l.target_id for l in tc_links if l.target_type == "test_case"]
        tc_keys: list[str] = []
        version_labels: list[str] = []
        results: list[str] = []
        for tc_id in tc_ids:
            tc = await session.get(TestCase, tc_id)
            if tc is None:
                continue
            tc_keys.append(tc.key)
            ct_stmt = select(CycleTest).where(
                CycleTest.test_case_id == tc_id, CycleTest.removed_at.is_(None)
            )
            if cycle_id:
                ct_stmt = ct_stmt.where(CycleTest.cycle_id == cycle_id)
            elif release_id:
                ct_stmt = ct_stmt.join(TestCycle, TestCycle.id == CycleTest.cycle_id).where(
                    TestCycle.release_id == release_id
                )
            cts = list(await session.scalars(ct_stmt))
            for ct in cts:
                if ct.test_case_version_id:
                    v = await session.get(TestCaseVersion, ct.test_case_version_id)
                    if v:
                        version_labels.append(f"{tc.key} v{v.version_number}")
                res = await resolve_cycle_test_result(session, ct.id)
                results.append(res.displayed_result)
        rows.append(
            MatrixRow(
                requirement_id=req.id,
                requirement_key=req.key,
                requirement_title=req.title,
                requirement_status=req.status,
                linked_test_case_keys=tc_keys,
                planned_version_labels=version_labels,
                latest_results=results,
                open_critical_defects=0,
            )
        )
    return rows
