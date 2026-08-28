"""Reporting endpoints (increment 9). Same query layer as the matrix and CSV."""

from __future__ import annotations

import csv
import io
import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentActor, DbSession
from app.domain import reporting
from app.domain.reporting import Scope

router = APIRouter(tags=["reporting"])


def _scope(project_id: str, release_id, plan_id, cycle_id, environment, build) -> Scope:
    return Scope(
        project_id=uuid.UUID(project_id),
        release_id=uuid.UUID(release_id) if release_id else None,
        plan_id=uuid.UUID(plan_id) if plan_id else None,
        cycle_id=uuid.UUID(cycle_id) if cycle_id else None,
        environment=environment,
        build=build,
    )


@router.get("/projects/{project_id}/reports/summary")
async def summary(
    project_id: str, actor: CurrentActor, db: DbSession,
    release_id: str | None = None, plan_id: str | None = None, cycle_id: str | None = None,
    environment: str | None = None, build: str | None = None,
) -> dict:
    scope = _scope(project_id, release_id, plan_id, cycle_id, environment, build)
    return await reporting.summary(db, actor, scope)


@router.get("/projects/{project_id}/reports/summary.csv")
async def summary_csv(
    project_id: str, actor: CurrentActor, db: DbSession,
    release_id: str | None = None, plan_id: str | None = None, cycle_id: str | None = None,
    environment: str | None = None, build: str | None = None,
) -> StreamingResponse:
    scope = _scope(project_id, release_id, plan_id, cycle_id, environment, build)
    metrics = await reporting.compute_all(db, actor, scope)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["metric_id", "label", "numerator", "denominator", "value", "display", "formula_version"])
    for m in metrics:
        j = m.to_json(scope)
        w.writerow([m.metric_id, m.label, m.numerator, m.denominator, m.value, j["display"], m.formula_version])
    buf.seek(0)
    fname = f"tesqivo_report_fv{reporting.FORMULA_VERSION}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/projects/{project_id}/reports/{metric_id}/drill-down")
async def drill_down(
    project_id: str, metric_id: str, actor: CurrentActor, db: DbSession,
    release_id: str | None = None, plan_id: str | None = None, cycle_id: str | None = None,
    environment: str | None = None, build: str | None = None,
) -> dict:
    """The exact contributing records behind a dashboard number (PRS §9)."""
    scope = _scope(project_id, release_id, plan_id, cycle_id, environment, build)
    return await reporting.drill_down(db, actor, scope, metric_id.upper())
