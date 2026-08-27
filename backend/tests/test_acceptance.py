"""Acceptance criteria (PRS §19). Builds metric Fixture A (docs/architecture/
17_metric_fixtures.md) end-to-end through the public API and asserts §19.3-§19.6.
"""

import pytest


async def _make_active_test_case(admin, project, title, steps):
    r = await admin.post(
        f"/api/v1/projects/{project['id']}/test-cases", json={"title": title, "steps": steps}
    )
    tc = r.json()
    for to in ("in_review", "approved"):
        r = await admin.post(
            f"/api/v1/test-cases/{tc['id']}/version-transitions",
            json={"to": to, "expected_version": tc["version"]},
        )
        tc = r.json()
    r = await admin.post(
        f"/api/v1/test-cases/{tc['id']}/lifecycle-transitions",
        json={"to": "active", "expected_version": tc["version"]},
    )
    return r.json()


async def _activate_requirement(admin, project, title, release_id=None):
    r = await admin.post(
        f"/api/v1/projects/{project['id']}/requirements",
        json={"title": title, "release_id": release_id},
    )
    req = r.json()
    r = await admin.post(
        f"/api/v1/requirements/{req['id']}/transitions",
        json={"to": "active", "expected_version": req["version"]},
    )
    return r.json()


async def _run_attempt(admin, cycle_test_id, results):
    r = await admin.post(f"/api/v1/cycle-tests/{cycle_test_id}/attempts")
    attempt = r.json()
    for i, res in enumerate(results, start=1):
        r = await admin.patch(
            f"/api/v1/attempts/{attempt['id']}/steps/{i}", json={"result": res}
        )
        assert r.status_code == 200, r.text
    r = await admin.post(f"/api/v1/attempts/{attempt['id']}/complete", json={})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def steps2():
    return [
        {"action": "step 1", "expected_result": "ok 1"},
        {"action": "step 2", "expected_result": "ok 2"},
    ]


@pytest.mark.asyncio
async def test_fixture_a_full_flow_and_metrics(admin, project, steps2):
    pid = project["id"]

    # Release + two active requirements linked to it
    rel = (await admin.post(f"/api/v1/projects/{pid}/releases", json={"name": "R1"})).json()
    await admin.post(
        f"/api/v1/releases/{rel['id']}/transitions",
        json={"to": "active", "expected_version": rel["version"]},
    )
    req1 = await _activate_requirement(admin, project, "Req one", rel["id"])
    req2 = await _activate_requirement(admin, project, "Req two", rel["id"])

    # Two active test cases
    tc1 = await _make_active_test_case(admin, project, "TC one", steps2)
    tc2 = await _make_active_test_case(admin, project, "TC two", steps2)

    # Requirement -> Test Case links (req1->tc1, req2->tc2)
    for req, tc in ((req1, tc1), (req2, tc2)):
        r = await admin.post(
            f"/api/v1/projects/{pid}/trace-links",
            json={
                "source_type": "requirement", "source_id": req["id"],
                "target_type": "test_case", "target_id": tc["id"],
            },
        )
        assert r.status_code == 201, r.text

    # Plan + scope + cycle
    plan = (
        await admin.post(
            f"/api/v1/projects/{pid}/plans", json={"name": "P1", "release_id": rel["id"]}
        )
    ).json()
    await admin.post(
        f"/api/v1/plans/{plan['id']}/scope",
        json={"test_case_ids": [tc1["id"], tc2["id"]]},
    )
    cycle = (
        await admin.post(
            f"/api/v1/plans/{plan['id']}/cycles",
            json={"name": "C1", "environment": "staging", "build": "1001", "release_id": rel["id"]},
        )
    ).json()
    r = await admin.post(
        f"/api/v1/cycles/{cycle['id']}/tests",
        json={"test_case_ids": [tc1["id"], tc2["id"]]},
    )
    assert r.status_code == 201, r.text
    ct_ids = r.json()["cycle_test_ids"]

    # Activate cycle -> snapshots approved versions
    r = await admin.post(
        f"/api/v1/cycles/{cycle['id']}/transitions",
        json={"to": "active", "expected_version": cycle["version"]},
    )
    assert r.status_code == 200, r.text

    cts = (await admin.get(f"/api/v1/cycles/{cycle['id']}/tests")).json()["items"]
    by_tc = {c["test_case_id"]: c["id"] for c in cts}

    # TC1 passes, TC2 fails
    await _run_attempt(admin, by_tc[tc1["id"]], ["passed", "passed"])
    fail_attempt = await _run_attempt(admin, by_tc[tc2["id"]], ["passed", "failed"])
    assert fail_attempt["overall_result"] == "FAILED"

    # Critical open defect linked from TC2's attempt and to Req two
    defect = (
        await admin.post(
            f"/api/v1/projects/{pid}/defects",
            json={"summary": "boom", "severity": "critical", "release_id": rel["id"]},
        )
    ).json()
    await admin.post(
        f"/api/v1/defects/{defect['id']}/transitions",
        json={"to": "open", "expected_version": defect["version"]},
    )
    await admin.post(
        f"/api/v1/attempts/{fail_attempt['id']}/defects", json={"defect_id": defect["id"]}
    )
    await admin.post(
        f"/api/v1/projects/{pid}/trace-links",
        json={
            "source_type": "defect", "source_id": defect["id"],
            "target_type": "requirement", "target_id": req2["id"],
        },
    )

    # --- §19.5 metric assertions ---
    summary = (
        await admin.get(
            f"/api/v1/projects/{pid}/reports/summary",
            params={"release_id": rel["id"], "cycle_id": cycle["id"],
                    "environment": "staging", "build": "1001"},
        )
    ).json()
    m = {row["metric_id"]: row for row in summary["metrics"]}

    assert m["M-01"]["value"] == 2
    assert m["M-02"]["display"] == "100.0%"
    assert m["M-03"]["display"] == "50.0%"
    assert m["M-04"]["value"] == 0
    assert m["M-05"]["display"] == "100.0%"
    assert m["M-06"]["display"] == "100.0%"
    assert m["M-07"]["display"] == "100.0%"
    assert m["M-08"]["display"] == "0.0%"
    assert m["M-09"]["value"] == 0
    assert m["M-10"]["value"] == 1
    assert m["M-11"]["value"] == 1
    assert m["M-13"]["display"] == "100.0%"

    # --- §19.6 cross-surface equality: CSV == summary ---
    csv_text = (
        await admin.get(
            f"/api/v1/projects/{pid}/reports/summary.csv",
            params={"release_id": rel["id"], "cycle_id": cycle["id"],
                    "environment": "staging", "build": "1001"},
        )
    ).text
    rows = [line.split(",") for line in csv_text.strip().splitlines()[1:]]
    csv_display = {r[0]: r[5] for r in rows}
    for mid, row in m.items():
        assert csv_display[mid] == row["display"], mid

    # --- §19.4 controlled edit after execution keeps the executed snapshot ---
    r = await admin.patch(
        f"/api/v1/test-cases/{tc1['id']}",
        json={"expected_version": tc1["version"], "title": "TC one - reworded",
              "change_summary": "post-exec edit"},
    )
    assert r.status_code == 200, r.text
    ct1_attempt = (await admin.get(f"/api/v1/cycles/{cycle['id']}/tests")).json()["items"]
    ct1 = next(c for c in ct1_attempt if c["test_case_id"] == tc1["id"])
    attempt = (await admin.get(f"/api/v1/attempts/{ct1['authoritative_attempt_id']}")).json()
    # the completed attempt still shows the original two snapshot steps, unchanged
    assert [s["action"] for s in attempt["steps"]] == ["step 1", "step 2"]
    assert attempt["status"] == "PASSED"


@pytest.mark.asyncio
async def test_fixture_b_half_coverage(admin, project, steps2):
    pid = project["id"]
    rel = (await admin.post(f"/api/v1/projects/{pid}/releases", json={"name": "R"})).json()
    await admin.post(f"/api/v1/releases/{rel['id']}/transitions",
                     json={"to": "active", "expected_version": rel["version"]})
    covered = await _activate_requirement(admin, project, "covered", rel["id"])
    await _activate_requirement(admin, project, "uncovered", rel["id"])
    tc = await _make_active_test_case(admin, project, "the test", steps2)
    await admin.post(
        f"/api/v1/projects/{pid}/trace-links",
        json={"source_type": "requirement", "source_id": covered["id"],
              "target_type": "test_case", "target_id": tc["id"]},
    )
    summary = (await admin.get(f"/api/v1/projects/{pid}/reports/summary")).json()
    m = {row["metric_id"]: row for row in summary["metrics"]}
    assert m["M-05"]["display"] == "50.0%"
    assert m["M-09"]["value"] == 1
