"""Release maintenance + release-wise execution roll-up."""

import pytest

from tests.test_execution import _ready_cycle_test


@pytest.mark.asyncio
async def test_create_edit_and_transition_release(admin, project):
    pid = project["id"]
    r = await admin.post(
        f"/api/v1/projects/{pid}/releases",
        json={"name": "2026.06", "version_label": "v2026.06",
              "start_date": "2026-06-01T00:00:00Z", "end_date": "2026-06-30T00:00:00Z"},
    )
    assert r.status_code == 201, r.text
    rel = r.json()
    assert rel["start_date"].startswith("2026-06-01")

    r = await admin.patch(
        f"/api/v1/releases/{rel['id']}",
        json={"expected_version": rel["version"], "name": "2026.06 — Summer",
              "description": "Summer release", "end_date": "2026-07-15T00:00:00Z"},
    )
    assert r.status_code == 200, r.text
    rel = r.json()
    assert rel["name"] == "2026.06 — Summer"
    assert rel["end_date"].startswith("2026-07-15")

    # stale version -> conflict
    r = await admin.patch(f"/api/v1/releases/{rel['id']}", json={"expected_version": 1, "name": "x"})
    assert r.status_code == 409

    # end before start -> validation error
    r = await admin.patch(
        f"/api/v1/releases/{rel['id']}",
        json={"expected_version": rel["version"], "start_date": "2026-08-01T00:00:00Z",
              "end_date": "2026-07-01T00:00:00Z"},
    )
    assert r.status_code == 422

    r = await admin.patch(
        f"/api/v1/releases/{rel['id']}",
        json={"expected_version": rel["version"], "clear_end_date": True},
    )
    assert r.json()["end_date"] is None

    rel = r.json()
    r = await admin.post(f"/api/v1/releases/{rel['id']}/transitions",
                         json={"to": "active", "expected_version": rel["version"]})
    assert r.status_code == 200
    rel = r.json()
    r = await admin.post(f"/api/v1/releases/{rel['id']}/transitions",
                         json={"to": "released", "expected_version": rel["version"]})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_release_overview_rolls_up_cycles(admin, project):
    pid = project["id"]
    rel = (await admin.post(f"/api/v1/projects/{pid}/releases", json={"name": "R1"})).json()
    await admin.post(f"/api/v1/releases/{rel['id']}/transitions",
                     json={"to": "active", "expected_version": rel["version"]})

    # a cycle attached to the release, with one passed execution
    tc, cyc, ct_id = await _ready_cycle_test(admin, project)
    # attach cycle to the release via a fresh cycle on a plan tied to the release
    plan = (await admin.post(f"/api/v1/projects/{pid}/plans",
                             json={"name": "P", "release_id": rel["id"]})).json()
    cyc2 = (await admin.post(f"/api/v1/plans/{plan['id']}/cycles",
                             json={"name": "C2", "environment": "e", "build": "b",
                                   "release_id": rel["id"]})).json()
    await admin.post(f"/api/v1/cycles/{cyc2['id']}/tests", json={"test_case_ids": [tc["id"]]})
    await admin.post(f"/api/v1/cycles/{cyc2['id']}/transitions",
                     json={"to": "active", "expected_version": cyc2["version"]})
    cts = (await admin.get(f"/api/v1/cycles/{cyc2['id']}/tests")).json()["items"]
    a = (await admin.post(f"/api/v1/cycle-tests/{cts[0]['id']}/attempts")).json()
    for i in range(1, len(a["steps"]) + 1):
        await admin.patch(f"/api/v1/attempts/{a['id']}/steps/{i}", json={"result": "passed"})
    await admin.post(f"/api/v1/attempts/{a['id']}/complete", json={})

    r = await admin.get(f"/api/v1/projects/{pid}/reports/release-overview")
    assert r.status_code == 200
    releases = r.json()["releases"]
    row = next(x for x in releases if x["release_id"] == rel["id"])
    assert row["cycle_count"] == 1
    assert row["scoped_tests"] == 1
    assert row["passed"] == 1
    assert row["completion"] == 1.0
    assert len(row["cycles"]) == 1
    assert row["cycles"][0]["cycle_key"] == cyc2["key"]

    # cycles list can be filtered by release
    filtered = (await admin.get(f"/api/v1/projects/{pid}/cycles", params={"release_id": rel["id"]})).json()
    assert [c["key"] for c in filtered] == [cyc2["key"]]
