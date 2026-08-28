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

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import Actor
from app.domain import authz
from app.domain.execution import resolve_cycle_test_result
from app.models import (
    AttemptDefectLink,
    CycleTest,
    Defect,
    ExecutionAttempt,
    Release,
    Requirement,
    Scenario,
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


async def _requirement_test_case_ids(
    session: AsyncSession, project_id: uuid.UUID, req_id: uuid.UUID
) -> set[uuid.UUID]:
    """Test cases that cover a requirement: direct ``covers`` trace links OR test
    cases in an active Scenario under the requirement (Requirement -> Scenario ->
    Test Case flow)."""
    direct = await session.scalars(
        select(TraceLink.target_id).where(
            TraceLink.project_id == project_id,
            TraceLink.removed_at.is_(None),
            TraceLink.source_type == "requirement",
            TraceLink.source_id == req_id,
            TraceLink.target_type == "test_case",
        )
    )
    via_scenario = await session.scalars(
        select(TestCase.id)
        .join(Scenario, Scenario.id == TestCase.scenario_id)
        .where(Scenario.requirement_id == req_id, Scenario.status == "active")
    )
    return set(direct) | set(via_scenario)


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

    # active Requirement -> covered logical test case ids (direct links + scenarios)
    req_to_tcs: dict[uuid.UUID, set[uuid.UUID]] = {}
    for req in active_reqs:
        req_to_tcs[req.id] = await _requirement_test_case_ids(session, scope.project_id, req.id)

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


async def cycle_breakdown(session: AsyncSession, actor: Actor, scope: Scope) -> list[dict]:
    """Execution progress per cycle in the selected scope - one row per cycle so
    the dashboard can group execution by cycle and link straight to it."""
    authz.authorize(actor, "report.view", project_id=scope.project_id)
    cts = await _scoped_cycle_tests(session, scope)
    by_cycle: dict[uuid.UUID, list[CycleTest]] = {}
    for ct in cts:
        by_cycle.setdefault(ct.cycle_id, []).append(ct)

    rows: list[dict] = []
    for cycle_id, cyc_cts in by_cycle.items():
        cycle = await session.get(TestCycle, cycle_id)
        if cycle is None:
            continue
        results = [
            (await resolve_cycle_test_result(session, ct.id)).displayed_result for ct in cyc_cts
        ]
        scoped = len(cyc_cts)
        terminal = sum(1 for r in results if r in _TERMINAL)
        passed = results.count("PASSED")
        failed = results.count("FAILED")
        blocked = results.count("BLOCKED")
        not_run = sum(1 for r in results if r in ("NOT_RUN", "RETEST_PENDING"))
        pass_den = passed + failed + blocked
        rows.append(
            {
                "cycle_id": str(cycle_id),
                "cycle_key": cycle.key,
                "name": cycle.name,
                "environment": cycle.environment,
                "build": cycle.build,
                "status": cycle.status,
                "scoped": scoped,
                "terminal": terminal,
                "passed": passed,
                "failed": failed,
                "blocked": blocked,
                "not_run": not_run,
                "completion": (terminal / scoped) if scoped else None,
                "pass_rate": (passed / pass_den) if pass_den else None,
            }
        )
    rows.sort(key=lambda r: r["cycle_key"])
    return rows


async def coverage_by_type(session: AsyncSession, actor: Actor, scope: Scope) -> dict:
    """Manual vs automated view of the repository and of requirement coverage."""
    authz.authorize(actor, "report.view", project_id=scope.project_id)
    tests = list(
        await session.scalars(
            select(TestCase).where(
                TestCase.project_id == scope.project_id,
                TestCase.lifecycle_state.in_(("approved", "active")),
            )
        )
    )
    automated = [t for t in tests if t.automation_status == "automated"]
    manual = [t for t in tests if t.automation_status == "candidate"]
    not_applicable = [t for t in tests if t.automation_status == "not_applicable"]

    active_reqs = list(
        await session.scalars(
            select(Requirement).where(
                Requirement.project_id == scope.project_id, Requirement.status == "active"
            )
        )
    )
    tc_by_id = {t.id: t for t in tests}
    reqs_auto = 0
    reqs_manual = 0
    for req in active_reqs:
        linked = await _requirement_test_case_ids(session, scope.project_id, req.id)
        kinds = {
            tc_by_id[tid].automation_status
            for tid in linked
            if tid in tc_by_id and _tc_qualifies(tc_by_id[tid])
        }
        if "automated" in kinds:
            reqs_auto += 1
        if "candidate" in kinds:
            reqs_manual += 1

    eligible = len(automated) + len(manual)
    return {
        "scope": scope.as_dict(),
        "formula_version": FORMULA_VERSION,
        "tests": {
            "automated": len(automated),
            "manual": len(manual),
            "not_applicable": len(not_applicable),
            "total": len(tests),
            "automation_ratio": (len(automated) / eligible) if eligible else None,
        },
        "requirement_coverage": {
            "active_requirements": len(active_reqs),
            "covered_by_automated": reqs_auto,
            "covered_by_manual": reqs_manual,
            "automated_ratio": (reqs_auto / len(active_reqs)) if active_reqs else None,
            "manual_ratio": (reqs_manual / len(active_reqs)) if active_reqs else None,
        },
    }


async def release_overview(
    session: AsyncSession, actor: Actor, project_id: uuid.UUID
) -> list[dict]:
    """One execution roll-up per non-archived release, with the release's cycle
    history - so the dashboard can show release-wise execution."""
    authz.authorize(actor, "report.view", project_id=project_id)
    releases = list(
        await session.scalars(
            select(Release)
            .where(Release.project_id == project_id, Release.status != "archived")
            .order_by(Release.key)
        )
    )
    out: list[dict] = []
    for rel in releases:
        cycles = await cycle_breakdown(session, actor, Scope(project_id=project_id, release_id=rel.id))
        scoped = sum(c["scoped"] for c in cycles)
        terminal = sum(c["terminal"] for c in cycles)
        passed = sum(c["passed"] for c in cycles)
        failed = sum(c["failed"] for c in cycles)
        blocked = sum(c["blocked"] for c in cycles)
        pass_den = passed + failed + blocked
        req_count = await session.scalar(
            select(func.count())
            .select_from(Requirement)
            .where(Requirement.project_id == project_id, Requirement.release_id == rel.id)
        )
        crit = await session.scalar(
            select(func.count())
            .select_from(Defect)
            .where(
                Defect.project_id == project_id,
                Defect.release_id == rel.id,
                Defect.severity == "critical",
                Defect.status.notin_(("closed", "rejected")),
            )
        )
        out.append(
            {
                "release_id": str(rel.id),
                "release_key": rel.key,
                "name": rel.name,
                "status": rel.status,
                "version_label": rel.version_label,
                "start_date": rel.start_date.isoformat() if rel.start_date else None,
                "end_date": rel.end_date.isoformat() if rel.end_date else None,
                "cycle_count": len(cycles),
                "cycles": cycles,
                "scoped_tests": scoped,
                "terminal": terminal,
                "passed": passed,
                "failed": failed,
                "blocked": blocked,
                "completion": (terminal / scoped) if scoped else None,
                "pass_rate": (passed / pass_den) if pass_den else None,
                "requirements": req_count or 0,
                "open_critical_defects": crit or 0,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Drill-down: every dashboard number resolves to its contributing records
# (PRS §9 "Every metric supports drill-down to its exact contributing records";
# acceptance §19.6 "every count drills down to its contributors").
# ---------------------------------------------------------------------------

METRIC_HELP = {
    "M-01": "Distinct cycle tests in the selected scope.",
    "M-02": "Cycle tests with a finished result (passed, failed, blocked, skipped, aborted).",
    "M-03": "Passed / (passed + failed + blocked).",
    "M-04": "Cycle tests with no attempt yet.",
    "M-05": "Active requirements with at least one approved/active linked test.",
    "M-06": "Active requirements covered by a test in the selected plan/cycle scope.",
    "M-07": "Active requirements whose linked in-scope test has been executed.",
    "M-08": "Active requirements for which every qualifying in-scope test passed.",
    "M-09": "Active requirements with no qualifying linked test.",
    "M-10": "Distinct critical defects that are not closed or rejected.",
    "M-11": "Active requirements linked to an open/in-progress critical or high defect.",
    "M-12": "Automated / automation-eligible active tests.",
    "M-13": "Resolvable / total active trace links.",
}
METRIC_LABELS = {
    "M-01": "Tests in scope", "M-02": "Execution complete", "M-03": "Pass rate",
    "M-04": "Not started", "M-05": "Design coverage", "M-06": "Plan coverage",
    "M-07": "Execution coverage", "M-08": "Pass coverage", "M-09": "Uncovered requirements",
    "M-10": "Open critical defects", "M-11": "Requirements at risk",
    "M-12": "Automation coverage", "M-13": "Trace-link health",
}


async def drill_down(
    session: AsyncSession, actor: Actor, scope: Scope, metric_id: str
) -> dict:
    authz.authorize(actor, "report.view", project_id=scope.project_id)
    if metric_id not in METRIC_LABELS:
        from app.core.errors import ResourceNotFound

        raise ResourceNotFound(f"Unknown metric '{metric_id}'.")

    cts = await _scoped_cycle_tests(session, scope)
    tc_by_id: dict[uuid.UUID, TestCase] = {}
    cyc_by_id: dict[uuid.UUID, TestCycle] = {}
    for ct in cts:
        if ct.test_case_id not in tc_by_id:
            tc_by_id[ct.test_case_id] = await session.get(TestCase, ct.test_case_id)
        if ct.cycle_id not in cyc_by_id:
            cyc_by_id[ct.cycle_id] = await session.get(TestCycle, ct.cycle_id)
    results: dict[uuid.UUID, str] = {
        ct.id: (await resolve_cycle_test_result(session, ct.id)).displayed_result for ct in cts
    }
    active_reqs = list(
        await session.scalars(
            select(Requirement).where(
                Requirement.project_id == scope.project_id, Requirement.status == "active"
            )
        )
    )
    req_to_tcs: dict[uuid.UUID, set[uuid.UUID]] = {}
    for req in active_reqs:
        req_to_tcs[req.id] = await _requirement_test_case_ids(session, scope.project_id, req.id)
    for ids in req_to_tcs.values():
        for tc_id in ids:
            if tc_id not in tc_by_id:
                tc_by_id[tc_id] = await session.get(TestCase, tc_id)
    cts_by_tc: dict[uuid.UUID, list[CycleTest]] = {}
    for ct in cts:
        cts_by_tc.setdefault(ct.test_case_id, []).append(ct)

    def qualifying_tc_keys(req_id: uuid.UUID) -> list[str]:
        return [
            tc_by_id[t].key
            for t in req_to_tcs.get(req_id, set())
            if (tc := tc_by_id.get(t)) is not None and _tc_qualifies(tc)
        ]

    def req_scoped_cts(req_id: uuid.UUID) -> list[CycleTest]:
        out: list[CycleTest] = []
        for t in req_to_tcs.get(req_id, set()):
            tc = tc_by_id.get(t)
            if tc and _tc_qualifies(tc):
                out.extend(cts_by_tc.get(t, []))
        return out

    def tc_link(tc: TestCase | None):
        return {"kind": "test_case", "id": str(tc.id), "key": tc.key} if tc else None

    def ct_row(ct: CycleTest, extra: dict | None = None) -> dict:
        tc = tc_by_id.get(ct.test_case_id)
        cyc = cyc_by_id.get(ct.cycle_id)
        cells = {
            "test": f"{tc.key} — {tc.title}" if tc else str(ct.test_case_id),
            "cycle": cyc.key if cyc else "",
            "env": f"{cyc.environment}/{cyc.build}" if cyc else "",
            "result": results.get(ct.id, "NOT_RUN"),
        }
        if extra:
            cells.update(extra)
        return {"cells": cells, "link": tc_link(tc)}

    columns: list[dict] = []
    rows: list[dict] = []

    if metric_id in ("M-01", "M-02", "M-03"):
        columns = [
            {"key": "test", "label": "Test"},
            {"key": "cycle", "label": "Cycle"},
            {"key": "env", "label": "Env / Build"},
            {"key": "result", "label": "Result"},
        ]
        pool = cts
        if metric_id == "M-03":
            pool = [c for c in cts if results[c.id] in ("PASSED", "FAILED", "BLOCKED")]
        rows = [ct_row(c) for c in sorted(pool, key=lambda c: tc_by_id.get(c.test_case_id).key if tc_by_id.get(c.test_case_id) else "")]

    elif metric_id == "M-04":
        columns = [
            {"key": "test", "label": "Test"},
            {"key": "cycle", "label": "Cycle"},
            {"key": "env", "label": "Env / Build"},
        ]
        for c in cts:
            has = await session.scalar(
                select(ExecutionAttempt.id).where(ExecutionAttempt.cycle_test_id == c.id).limit(1)
            )
            if has is None:
                r = ct_row(c)
                r["cells"].pop("result", None)
                rows.append(r)

    elif metric_id in ("M-05", "M-06", "M-07", "M-08", "M-09"):
        columns = [
            {"key": "requirement", "label": "Requirement"},
            {"key": "status", "label": "In this metric"},
            {"key": "tests", "label": "Qualifying tests"},
        ]
        for req in sorted(active_reqs, key=lambda r: r.key):
            qkeys = qualifying_tc_keys(req.id)
            scoped = req_scoped_cts(req.id)
            scoped_results = [results[c.id] for c in scoped]
            if metric_id == "M-05":
                inc = bool(qkeys)
            elif metric_id == "M-06":
                inc = bool(scoped)
            elif metric_id == "M-07":
                inc = any(r in _TERMINAL for r in scoped_results)
            elif metric_id == "M-08":
                if not scoped:
                    continue  # not in denominator
                inc = bool(scoped_results) and all(r in ("PASSED", "SKIPPED") for r in scoped_results) and any(r == "PASSED" for r in scoped_results)
            else:  # M-09
                inc = not qkeys
            if metric_id == "M-09" and not inc:
                continue
            if metric_id == "M-06":
                scoped_keys = sorted(
                    {tc_by_id[c.test_case_id].key for c in scoped if tc_by_id.get(c.test_case_id)}
                )
                tests_cell = ", ".join(scoped_keys) or "—"
            else:
                tests_cell = ", ".join(qkeys) or "—"
            rows.append(
                {
                    "cells": {
                        "requirement": f"{req.key} — {req.title}",
                        "status": "counted" if inc else "not counted",
                        "tests": tests_cell,
                    },
                    "link": None,
                }
            )

    elif metric_id == "M-10":
        columns = [
            {"key": "defect", "label": "Defect"},
            {"key": "severity", "label": "Severity"},
            {"key": "status", "label": "Status"},
        ]
        crit = await session.scalars(
            select(Defect).where(
                Defect.project_id == scope.project_id,
                Defect.severity == "critical",
                Defect.status.notin_(("closed", "rejected")),
            )
        )
        for d in sorted(crit, key=lambda d: d.key):
            rows.append(
                {
                    "cells": {"defect": f"{d.key} — {d.summary}", "severity": d.severity, "status": d.status},
                    "link": None,
                }
            )

    elif metric_id == "M-11":
        columns = [
            {"key": "requirement", "label": "Requirement"},
            {"key": "via", "label": "Linked defect(s)"},
        ]
        hot = {
            r.id: r
            for r in await session.scalars(
                select(Defect).where(
                    Defect.project_id == scope.project_id,
                    Defect.severity.in_(("critical", "high")),
                    Defect.status.in_(("open", "in_progress")),
                )
            )
        }
        for req in sorted(active_reqs, key=lambda r: r.key):
            via: set[str] = set()
            direct = await session.scalars(
                select(TraceLink.source_id).where(
                    TraceLink.project_id == scope.project_id,
                    TraceLink.removed_at.is_(None),
                    TraceLink.source_type == "defect",
                    TraceLink.target_type == "requirement",
                    TraceLink.target_id == req.id,
                )
            )
            for did in direct:
                if did in hot:
                    via.add(f"{hot[did].key} (direct)")
            for ct in req_scoped_cts(req.id):
                dids = await session.scalars(
                    select(AttemptDefectLink.defect_id)
                    .join(ExecutionAttempt, ExecutionAttempt.id == AttemptDefectLink.attempt_id)
                    .where(ExecutionAttempt.cycle_test_id == ct.id)
                )
                for did in dids:
                    if did in hot:
                        via.add(f"{hot[did].key} (via execution)")
            if via:
                rows.append(
                    {
                        "cells": {"requirement": f"{req.key} — {req.title}", "via": ", ".join(sorted(via))},
                        "link": None,
                    }
                )

    elif metric_id == "M-12":
        columns = [
            {"key": "test", "label": "Test"},
            {"key": "automation", "label": "Automation status"},
        ]
        eligible = await session.scalars(
            select(TestCase).where(
                TestCase.project_id == scope.project_id,
                TestCase.lifecycle_state == "active",
                TestCase.is_eligible_for_automation.is_(True),
                TestCase.automation_status != "not_applicable",
            )
        )
        for tc in sorted(eligible, key=lambda t: t.key):
            rows.append(
                {
                    "cells": {"test": f"{tc.key} — {tc.title}", "automation": tc.automation_status},
                    "link": tc_link(tc),
                }
            )

    else:  # M-13
        columns = [
            {"key": "source", "label": "Source"},
            {"key": "target", "label": "Target"},
            {"key": "type", "label": "Relationship"},
            {"key": "resolvable", "label": "Resolvable"},
        ]
        from app.domain.traceability import _entity_project

        links = await session.scalars(
            select(TraceLink).where(
                TraceLink.project_id == scope.project_id, TraceLink.removed_at.is_(None)
            )
        )
        for lk in links:
            sp = await _entity_project(session, lk.source_type, lk.source_id)
            tp = await _entity_project(session, lk.target_type, lk.target_id)
            ok = sp == scope.project_id and tp == scope.project_id
            rows.append(
                {
                    "cells": {
                        "source": f"{lk.source_type}",
                        "target": f"{lk.target_type}",
                        "type": lk.relationship_type,
                        "resolvable": "yes" if ok else "no",
                    },
                    "link": None,
                }
            )

    return {
        "metric_id": metric_id,
        "label": METRIC_LABELS[metric_id],
        "help": METRIC_HELP[metric_id],
        "scope": scope.as_dict(),
        "formula_version": FORMULA_VERSION,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
    }
