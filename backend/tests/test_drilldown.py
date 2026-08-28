"""Every dashboard number resolves to its contributing records (PRS §9, §19.6)."""

import pytest

from tests.test_acceptance import (
    _activate_requirement,
    _make_active_test_case,
    _run_attempt,
)


@pytest.fixture
def steps2():
    return [
        {"action": "s1", "expected_result": "e1"},
        {"action": "s2", "expected_result": "e2"},
    ]


@pytest.mark.asyncio
async def test_drilldown_rows_match_metric_numbers(admin, project, steps2):
    pid = project["id"]
    rel = (await admin.post(f"/api/v1/projects/{pid}/releases", json={"name": "R"})).json()
    await admin.post(f"/api/v1/releases/{rel['id']}/transitions",
                     json={"to": "active", "expected_version": rel["version"]})
    req1 = await _activate_requirement(admin, project, "req 1", rel["id"])
    req2 = await _activate_requirement(admin, project, "req 2", rel["id"])
    tc1 = await _make_active_test_case(admin, project, "tc 1", steps2)
    tc2 = await _make_active_test_case(admin, project, "tc 2", steps2)
    for req, tc in ((req1, tc1), (req2, tc2)):
        await admin.post(f"/api/v1/projects/{pid}/trace-links", json={
            "source_type": "requirement", "source_id": req["id"],
            "target_type": "test_case", "target_id": tc["id"]})

    plan = (await admin.post(f"/api/v1/projects/{pid}/plans", json={"name": "P"})).json()
    await admin.post(f"/api/v1/plans/{plan['id']}/scope", json={"test_case_ids": [tc1["id"], tc2["id"]]})
    cyc = (await admin.post(f"/api/v1/plans/{plan['id']}/cycles",
                            json={"name": "C", "environment": "staging", "build": "9"})).json()
    r = await admin.post(f"/api/v1/cycles/{cyc['id']}/tests", json={"test_case_ids": [tc1["id"], tc2["id"]]})
    await admin.post(f"/api/v1/cycles/{cyc['id']}/transitions",
                     json={"to": "active", "expected_version": cyc["version"]})
    cts = (await admin.get(f"/api/v1/cycles/{cyc['id']}/tests")).json()["items"]
    by_tc = {c["test_case_id"]: c["id"] for c in cts}
    await _run_attempt(admin, by_tc[tc1["id"]], ["passed", "passed"])
    await _run_attempt(admin, by_tc[tc2["id"]], ["passed", "failed"])

    params = {"cycle_id": cyc["id"]}
    summary = (await admin.get(f"/api/v1/projects/{pid}/reports/summary", params=params)).json()
    m = {row["metric_id"]: row for row in summary["metrics"]}

    async def dd(mid):
        r = await admin.get(f"/api/v1/projects/{pid}/reports/{mid}/drill-down", params=params)
        assert r.status_code == 200, r.text
        return r.json()

    # M-01 scoped tests: rows == the count
    assert (await dd("M-01"))["row_count"] == m["M-01"]["numerator"] == 2
    # M-03 pass rate denominator = passed+failed+blocked = 2 rows
    assert (await dd("M-03"))["row_count"] == m["M-03"]["denominator"] == 2
    # M-04 not started = 0
    assert (await dd("M-04"))["row_count"] == m["M-04"]["numerator"] == 0
    # M-05 design coverage: one row per active requirement (2), "counted" rows == numerator
    d5 = await dd("M-05")
    assert d5["row_count"] == m["M-05"]["denominator"] == 2
    assert sum(1 for r in d5["rows"] if r["cells"]["status"] == "counted") == m["M-05"]["numerator"] == 2
    # M-09 uncovered = 0 rows
    assert (await dd("M-09"))["row_count"] == m["M-09"]["numerator"] == 0
    # M-12 automation coverage: rows == eligible active tests (denominator)
    assert (await dd("M-12"))["row_count"] == m["M-12"]["denominator"]
    # M-13 trace-link health: rows == total active links (denominator)
    assert (await dd("M-13"))["row_count"] == m["M-13"]["denominator"] == 2

    # a drilled row carries a link to the underlying test case
    row = (await dd("M-01"))["rows"][0]
    assert row["link"]["kind"] == "test_case"
    assert row["link"]["key"].startswith("DEMO-TC-")


@pytest.mark.asyncio
async def test_drilldown_unknown_metric_is_404(admin, project):
    r = await admin.get(f"/api/v1/projects/{project['id']}/reports/M-99/drill-down")
    assert r.status_code == 404
