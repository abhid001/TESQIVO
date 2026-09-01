"""Add / remove tests from a cycle at any time (Draft / Active / Reopened)."""

import pytest

from tests.test_execution import _ready_cycle_test


async def _extra_active_tc(admin, project, title):
    steps = [{"action": "a", "expected_result": "b"}]
    r = await admin.post(f"/api/v1/projects/{project['id']}/test-cases", json={"title": title, "steps": steps})
    tc = r.json()
    for to in ("in_review", "approved"):
        tc = (await admin.post(
            f"/api/v1/test-cases/{tc['id']}/version-transitions",
            json={"to": to, "expected_version": tc["version"]},
        )).json()
    tc = (await admin.post(
        f"/api/v1/test-cases/{tc['id']}/lifecycle-transitions",
        json={"to": "active", "expected_version": tc["version"]},
    )).json()
    return tc


@pytest.mark.asyncio
async def test_add_and_remove_tests_from_active_cycle(admin, project):
    tc, cyc, ct_id = await _ready_cycle_test(admin, project)  # cycle is Active with 1 test
    other = await _extra_active_tc(admin, project, "second test")

    # add to an active cycle - snapshots immediately
    r = await admin.post(f"/api/v1/cycles/{cyc['id']}/tests", json={"test_case_ids": [other["id"]]})
    assert r.status_code == 201, r.text
    new_ct_id = r.json()["cycle_test_ids"][0]
    items = (await admin.get(f"/api/v1/cycles/{cyc['id']}/tests")).json()["items"]
    assert len(items) == 2
    assert all(i["test_case_version_id"] for i in items)  # both snapshotted
    assert {i["test_case_key"] for i in items} == {tc["key"], other["key"]}

    # remove one
    r = await admin.delete(f"/api/v1/cycle-tests/{new_ct_id}")
    assert r.status_code == 204
    items = (await admin.get(f"/api/v1/cycles/{cyc['id']}/tests")).json()["items"]
    assert len(items) == 1

    # can re-add the same test case afterwards
    r = await admin.post(f"/api/v1/cycles/{cyc['id']}/tests", json={"test_case_ids": [other["id"]]})
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_cannot_remove_test_with_in_progress_attempt(admin, project):
    _, cyc, ct_id = await _ready_cycle_test(admin, project)
    await admin.post(f"/api/v1/cycle-tests/{ct_id}/attempts")  # in progress
    r = await admin.delete(f"/api/v1/cycle-tests/{ct_id}")
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_cannot_change_scope_of_completed_cycle(admin, project):
    _, cyc, ct_id = await _ready_cycle_test(admin, project)
    cyc_now = [c for c in (await admin.get(f"/api/v1/projects/{project['id']}/cycles")).json() if c["id"] == cyc["id"]][0]
    await admin.post(
        f"/api/v1/cycles/{cyc['id']}/transitions",
        json={"to": "completed", "expected_version": cyc_now["version"]},
    )
    r = await admin.delete(f"/api/v1/cycle-tests/{ct_id}")
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_clone_cycle_copies_scope_as_fresh_draft(admin, project):
    tc, cyc, ct_id = await _ready_cycle_test(admin, project)  # Active cycle, 1 test
    # run the original so it has a result that must NOT carry over
    a = (await admin.post(f"/api/v1/cycle-tests/{ct_id}/attempts")).json()
    for i in range(1, len(a["steps"]) + 1):
        await admin.patch(f"/api/v1/attempts/{a['id']}/steps/{i}", json={"result": "passed"})
    await admin.post(f"/api/v1/attempts/{a['id']}/complete", json={})

    r = await admin.post(
        f"/api/v1/cycles/{cyc['id']}/clone",
        json={"name": "Regression round 2", "environment": "staging", "build": "42"},
    )
    assert r.status_code == 201, r.text
    clone = r.json()
    assert clone["id"] != cyc["id"]
    assert clone["status"] == "draft"
    assert clone["name"] == "Regression round 2"
    assert clone["environment"] == "staging" and clone["build"] == "42"

    items = (await admin.get(f"/api/v1/cycles/{clone['id']}/tests")).json()["items"]
    assert {i["test_case_key"] for i in items} == {tc["key"]}
    assert all(i["displayed_result"] == "NOT_RUN" for i in items)
    assert all(i["attempt_count"] == 0 for i in items)

    # defaults: name/env/build fall back to the source when omitted
    r2 = await admin.post(f"/api/v1/cycles/{cyc['id']}/clone", json={})
    assert r2.status_code == 201
    assert r2.json()["name"] == f"{cyc['name']} (copy)"


@pytest.mark.asyncio
async def test_cycle_breakdown_groups_execution_by_cycle(admin, project):
    _, cyc, ct_id = await _ready_cycle_test(admin, project)
    a = (await admin.post(f"/api/v1/cycle-tests/{ct_id}/attempts")).json()
    for i in range(1, len(a["steps"]) + 1):
        await admin.patch(f"/api/v1/attempts/{a['id']}/steps/{i}", json={"result": "passed"})
    await admin.post(f"/api/v1/attempts/{a['id']}/complete", json={})

    r = await admin.get(f"/api/v1/projects/{project['id']}/reports/cycle-breakdown")
    assert r.status_code == 200
    cycles = r.json()["cycles"]
    row = next(c for c in cycles if c["cycle_id"] == cyc["id"])
    assert row["scoped"] == 1
    assert row["passed"] == 1
    assert row["completion"] == 1.0
    assert row["cycle_key"] and row["name"]
