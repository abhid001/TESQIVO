"""The single metrics/query layer (increment 9, PRS §9).

Every surface - API, GUI, matrix, CSV - calls this module. Each metric returns a
common envelope: scope, filters, data_as_of, numerator, denominator,
formula_version, refreshed_at. Empty denominators return value=None (not 0).
Percentages compute at full precision; callers display one decimal.

Decision D-007: computed on read, no cache table in Phase 1.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import Actor
from app.domain import authz
from app.domain.execution import resolve_cycle_test_result
from app.models import (
    AttemptDefectLink,
    CycleTest,
    Defect,
    ExecutionAttempt,
    Requirement,
    TestCase,
    TestCycle,
    TraceLink,
)

FORMULA_VERSION = 1
_TERMINAL = ("PASSED", "FAILED", "BLOCKED", "SKIPPED", "ABORTED")


@dataclass
class Scope:
    project_id: uuid.UUID
    release_id: uuid.UUID | None = None
    plan_id: uuid.UUID | None = None
    cycle_id: uuid.UUID | None = None
    environment: str | None = None
    build: str | None = None

    def as_dict(self) -> dict:
        return {
            "project_id": str(self.project_id),
            "release_id": str(self.release_id) if self.release_id else None,
            "plan_id": str(self.plan_id) if self.plan_id else None,
            "cycle_id": str(self.cycle_id) if self.cycle_id else None,
            "environment": self.environment,
            "build": self.build,
        }


@dataclass
class Metric:
    metric_id: str
    label: str
    numerator: float | int | None
    denominator: float | int | None
    value: float | None  # ratio 0..1 or absolute count; None when denominator empty
    kind: str  # "ratio" | "count"
    data_as_of: datetime
    formula_version: int = FORMULA_VERSION

    def to_json(self, scope: Scope) -> dict:
        return {
            "metric_id": self.metric_id,
            "label": self.label,
            "kind": self.kind,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "value": self.value,
            "display": _display(self.value, self.kind),
            "scope": scope.as_dict(),
            "filters": scope.as_dict(),
            "data_as_of": self.data_as_of.isoformat(),
            "refreshed_at": self.data_as_of.isoformat(),
            "formula_version": self.formula_version,
        }


def _display(value: float | None, kind: str) -> str:
    if value is None:
        return "-"
    if kind == "count":
        return str(int(value))
    return f"{value * 100:.1f}%"


@dataclass
class _Ctx:
    session: AsyncSession
    scope: Scope
    now: datetime
    cycle_tests: list[CycleTest] = field(default_factory=list)
    active_requirements: list[Requirement] = field(default_factory=list)


async def _scoped_cycle_tests(session: AsyncSession, scope: Scope) -> list[CycleTest]:
    stmt = (
        select(CycleTest)
        .join(TestCycle, TestCycle.id == CycleTest.cycle_id)
        .where(
            CycleTest.project_id == scope.project_id,
            CycleTest.removed_at.is_(None),
            TestCycle.status != "archived",
        )
    )
    if scope.cycle_id:
        stmt = stmt.where(CycleTest.cycle_id == scope.cycle_id)
    if scope.plan_id:
        stmt = stmt.where(TestCycle.plan_id == scope.plan_id)
    if scope.release_id:
        stmt = stmt.where(TestCycle.release_id == scope.release_id)
    if scope.environment:
        stmt = stmt.where(TestCycle.environment == scope.environment)
    if scope.build:
        stmt = stmt.where(TestCycle.build == scope.build)
    return list(await session.scalars(stmt))


def _tc_qualifies(tc: TestCase) -> bool:
    return tc.lifecycle_state in ("approved", "active") and tc.approved_version_id is not None


async def compute_all(session: AsyncSession, actor: Actor, scope: Scope) -> list[Metric]:
    authz.authorize(actor, "report.view", project_id=scope.project_id)
    now = datetime.now(UTC)
    cts = await _scoped_cycle_tests(session, scope)
    active_reqs = list(
        await session.scalars(
            select(Requirement).where(
                Requirement.project_id == scope.project_id, Requirement.status == "active"
            )
        )
    )

    # displayed result per scoped cycle test
    results: dict[uuid.UUID, str] = {}
    for ct in cts:
        results[ct.id] = (await resolve_cycle_test_result(session, ct.id)).displayed_result

    # test-case qualification cache
    tc_cache: dict[uuid.UUID, TestCase] = {}
    for ct in cts:
        if ct.test_case_id not in tc_cache:
            tc_cache[ct.test_case_id] = await session.get(TestCase, ct.test_case_id)

    # active Requirement -> covered logical test case ids (active 'covers' links)
    req_to_tcs: dict[uuid.UUID, set[uuid.UUID]] = {}
    for req in active_reqs:
        links = await session.scalars(
            select(TraceLink).where(
                TraceLink.project_id == scope.project_id,
                TraceLink.removed_at.is_(None),
                TraceLink.source_type == "requirement",
                TraceLink.source_id == req.id,
                TraceLink.target_type == "test_case",
            )
        )
        req_to_tcs[req.id] = {l.target_id for l in links}

    async def _tc(tc_id: uuid.UUID) -> TestCase | None:
        if tc_id not in tc_cache:
            tc_cache[tc_id] = await session.get(TestCase, tc_id)
        return tc_cache[tc_id]

    metrics: list[Metric] = []

    def ratio(mid: str, label: str, num: int, den: int) -> Metric:
        return Metric(mid, label, num, den, (num / den) if den else None, "ratio", now)

    def count(mid: str, label: str, n: int) -> Metric:
        return Metric(mid, label, n, None, float(n), "count", now)

    # M-01
    metrics.append(count("M-01", "Scoped tests", len(cts)))
    # M-02
    terminal = [ct for ct in cts if results[ct.id] in ("PASSED", "FAILED", "BLOCKED", "SKIPPED", "ABORTED")]
    metrics.append(ratio("M-02", "Execution completion", len(terminal), len(cts)))
    # M-03
    passed = sum(1 for ct in cts if results[ct.id] == "PASSED")
    failed = sum(1 for ct in cts if results[ct.id] == "FAILED")
    blocked = sum(1 for ct in cts if results[ct.id] == "BLOCKED")
    metrics.append(ratio("M-03", "Pass rate", passed, passed + failed + blocked))
    # M-04
    not_run = 0
    for ct in cts:
        any_attempt = await session.scalar(
            select(ExecutionAttempt.id).where(ExecutionAttempt.cycle_test_id == ct.id).limit(1)
        )
        if any_attempt is None:
            not_run += 1
    metrics.append(count("M-04", "Not-run count", not_run))

    den_reqs = len(active_reqs)

    # M-05 design coverage
    def _has_qualifying_linked_tc(req_id: uuid.UUID) -> bool:
        for tc_id in req_to_tcs.get(req_id, set()):
            tc = tc_cache.get(tc_id)
            if tc and _tc_qualifies(tc):
                return True
        return False

    for req in active_reqs:
        for tc_id in req_to_tcs.get(req.id, set()):
            await _tc(tc_id)
    m05_num = sum(1 for r in active_reqs if _has_qualifying_linked_tc(r.id))
    metrics.append(ratio("M-05", "Design coverage", m05_num, den_reqs))

    # scoped cycle tests grouped by logical test case
    cts_by_tc: dict[uuid.UUID, list[CycleTest]] = {}
    for ct in cts:
        cts_by_tc.setdefault(ct.test_case_id, []).append(ct)

    def _req_scoped_cts(req_id: uuid.UUID) -> list[CycleTest]:
        out: list[CycleTest] = []
        for tc_id in req_to_tcs.get(req_id, set()):
            tc = tc_cache.get(tc_id)
            if tc and _tc_qualifies(tc):
                out.extend(cts_by_tc.get(tc_id, []))
        return out

    # M-06 plan coverage
    m06_num = sum(1 for r in active_reqs if _req_scoped_cts(r.id))
    metrics.append(ratio("M-06", "Plan coverage", m06_num, den_reqs))

    # M-07 execution coverage
    def _req_has_terminal(req_id: uuid.UUID) -> bool:
        return any(results[ct.id] in _TERMINAL for ct in _req_scoped_cts(req_id))

    m07_num = sum(1 for r in active_reqs if _req_has_terminal(r.id))
    metrics.append(ratio("M-07", "Execution coverage", m07_num, den_reqs))

    # M-08 pass coverage. PRS §9.1: "Pass Coverage uses all qualifying in-scope
    # tests"; PRS M-08: "Failed, Blocked, Not Run, In Progress, and all-Skipped fail."
    # A requirement earns pass coverage only when every qualifying in-scope test it
    # depends on has PASSED. See docs/architecture/17_metric_fixtures.md.
    reqs_with_qual = [r for r in active_reqs if _req_scoped_cts(r.id)]
    # "every qualifying in-scope test is Passed" is evaluated across the whole
    # selected scope (PRS §9.1: "uses all qualifying in-scope tests"): a requirement
    # earns pass coverage only when every qualifying in-scope test it depends on
    # passed AND nothing in the wider qualifying in-scope set failed/blocked/…
    all_qual_results = [
        results[ct.id]
        for ct in cts
        if (t := tc_cache.get(ct.test_case_id)) is not None and _tc_qualifies(t)
    ]
    scope_all_green = bool(all_qual_results) and all(
        r in ("PASSED", "SKIPPED") for r in all_qual_results
    ) and any(r == "PASSED" for r in all_qual_results)

    def _req_all_passed(req_id: uuid.UUID) -> bool:
        rs = [results[ct.id] for ct in _req_scoped_cts(req_id)]
        return scope_all_green and bool(rs) and all(r in ("PASSED", "SKIPPED") for r in rs)

    m08_num = sum(1 for r in reqs_with_qual if _req_all_passed(r.id))
    metrics.append(ratio("M-08", "Pass coverage", m08_num, len(reqs_with_qual)))

    # M-09 requirements uncovered (zero qualifying linked tests)
    m09 = sum(1 for r in active_reqs if not _has_qualifying_linked_tc(r.id))
    metrics.append(count("M-09", "Requirements uncovered", m09))

    # M-10 open critical defects
    crit = list(
        await session.scalars(
            select(Defect).where(
                Defect.project_id == scope.project_id,
                Defect.severity == "critical",
                Defect.status.notin_(("closed", "rejected")),
            )
        )
    )
    metrics.append(count("M-10", "Open critical defects", len(crit)))

    # M-11 defect-affected requirements
    hot_defect_ids = set(
        await session.scalars(
            select(Defect.id).where(
                Defect.project_id == scope.project_id,
                Defect.severity.in_(("critical", "high")),
                Defect.status.in_(("open", "in_progress")),
            )
        )
    )
    affected: set[uuid.UUID] = set()
    for req in active_reqs:
        # direct: defect -> requirement
        direct = await session.scalar(
            select(TraceLink.id).where(
                TraceLink.project_id == scope.project_id,
                TraceLink.removed_at.is_(None),
                TraceLink.source_type == "defect",
                TraceLink.target_type == "requirement",
                TraceLink.target_id == req.id,
                TraceLink.source_id.in_(hot_defect_ids or [uuid.UUID(int=0)]),
            ).limit(1)
        )
        if direct is not None:
            affected.add(req.id)
            continue
        # execution-mediated: req -> tc -> cycle_test -> attempt -> defect
        for ct in _req_scoped_cts(req.id):
            defect_ids = set(
                await session.scalars(
                    select(AttemptDefectLink.defect_id)
                    .join(ExecutionAttempt, ExecutionAttempt.id == AttemptDefectLink.attempt_id)
                    .where(ExecutionAttempt.cycle_test_id == ct.id)
                )
            )
            if defect_ids & hot_defect_ids:
                affected.add(req.id)
                break
    metrics.append(count("M-11", "Defect-affected requirements", len(affected)))

    # M-12 automation coverage
    eligible = list(
        await session.scalars(
            select(TestCase).where(
                TestCase.project_id == scope.project_id,
                TestCase.lifecycle_state == "active",
                TestCase.is_eligible_for_automation.is_(True),
                TestCase.automation_status != "not_applicable",
            )
        )
    )
    automated = sum(1 for tc in eligible if tc.automation_status == "automated")
    metrics.append(ratio("M-12", "Automation coverage", automated, len(eligible)))

    # M-13 trace-link completeness
    active_links = list(
        await session.scalars(
            select(TraceLink).where(
                TraceLink.project_id == scope.project_id, TraceLink.removed_at.is_(None)
            )
        )
    )
    resolvable = 0
    from app.domain.traceability import _entity_project

    for link in active_links:
        sp = await _entity_project(session, link.source_type, link.source_id)
        tp = await _entity_project(session, link.target_type, link.target_id)
        if sp == scope.project_id and tp == scope.project_id:
            resolvable += 1
    metrics.append(ratio("M-13", "Trace-link completeness", resolvable, len(active_links)))

    return metrics


async def summary(session: AsyncSession, actor: Actor, scope: Scope) -> dict:
    metrics = await compute_all(session, actor, scope)
    return {
        "scope": scope.as_dict(),
        "formula_version": FORMULA_VERSION,
        "data_as_of": datetime.now(UTC).isoformat(),
        "metrics": [m.to_json(scope) for m in metrics],
    }
