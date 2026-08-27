"""Increment 7: derivation, immutability, corrections, authoritative attempt, retest."""

import pytest

from app.domain.execution import derive_overall_result


class _S:
    def __init__(self, result, required=True):
        self.result = result
        self.is_required = required


def test_derivation_pure_function():
    assert derive_overall_result([_S("passed"), _S("passed")]) == "PASSED"
    assert derive_overall_result([_S("passed"), _S("failed")]) == "FAILED"
    assert derive_overall_result([_S("blocked"), _S("passed")]) == "BLOCKED"
    assert derive_overall_result([_S("failed"), _S("blocked")]) == "FAILED"  # failed wins
    assert derive_overall_result([_S("passed"), _S("skipped")]) == "PASSED"
    assert derive_overall_result([_S("passed"), _S("not_run")]) == "IN_PROGRESS"
    assert derive_overall_result([_S("failed", required=False), _S("passed")]) == "PASSED"


async def _ready_cycle_test(admin, project):
    steps = [{"action": "a", "expected_result": "b"}, {"action": "c", "expected_result": "d"}]
    r = await admin.post(
        f"/api/v1/projects/{project['id']}/test-cases", json={"title": "TC", "steps": steps}
    )
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
    plan = (await admin.post(f"/api/v1/projects/{project['id']}/plans", json={"name": "P"})).json()
    await admin.post(f"/api/v1/plans/{plan['id']}/scope", json={"test_case_ids": [tc["id"]]})
    cyc = (await admin.post(
        f"/api/v1/plans/{plan['id']}/cycles",
        json={"name": "C", "environment": "e", "build": "b"},
    )).json()
    r = await admin.post(f"/api/v1/cycles/{cyc['id']}/tests", json={"test_case_ids": [tc["id"]]})
    ct_id = r.json()["cycle_test_ids"][0]
    await admin.post(
        f"/api/v1/cycles/{cyc['id']}/transitions",
        json={"to": "active", "expected_version": cyc["version"]},
    )
    return tc, cyc, ct_id


@pytest.mark.asyncio
async def test_completed_attempt_is_immutable(admin, project):
    _, _, ct_id = await _ready_cycle_test(admin, project)
    a = (await admin.post(f"/api/v1/cycle-tests/{ct_id}/attempts")).json()
    for i in (1, 2):
        await admin.patch(f"/api/v1/attempts/{a['id']}/steps/{i}", json={"result": "passed"})
    a = (await admin.post(f"/api/v1/attempts/{a['id']}/complete", json={})).json()
    assert a["status"] == "PASSED"
    r = await admin.patch(f"/api/v1/attempts/{a['id']}/steps/1", json={"result": "failed"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_correction_is_append_only_and_changes_authoritative_result(admin, project):
    _, cyc, ct_id = await _ready_cycle_test(admin, project)
    a = (await admin.post(f"/api/v1/cycle-tests/{ct_id}/attempts")).json()
    await admin.patch(f"/api/v1/attempts/{a['id']}/steps/1", json={"result": "passed"})
    await admin.patch(f"/api/v1/attempts/{a['id']}/steps/2", json={"result": "failed"})
    a = (await admin.post(f"/api/v1/attempts/{a['id']}/complete", json={})).json()
    assert a["overall_result"] == "FAILED"

    r = await admin.post(
        f"/api/v1/attempts/{a['id']}/corrections",
        json={"new_value": "PASSED", "reason": "step 2 env issue, retested manually"},
    )
    assert r.status_code == 201
    corrected = r.json()
    # original evidence untouched
    assert corrected["overall_result"] == "FAILED"
    assert corrected["steps"][1]["result"] == "failed"
    assert corrected["corrections"][0]["new_value"] == "PASSED"

    # authoritative/displayed result now reflects the correction
    cts = (await admin.get(f"/api/v1/cycles/{cyc['id']}/tests")).json()["items"]
    assert cts[0]["displayed_result"] == "PASSED"


@pytest.mark.asyncio
async def test_retest_creates_new_attempt_without_mutating_earlier(admin, project):
    _, cyc, ct_id = await _ready_cycle_test(admin, project)
    a1 = (await admin.post(f"/api/v1/cycle-tests/{ct_id}/attempts")).json()
    await admin.patch(f"/api/v1/attempts/{a1['id']}/steps/1", json={"result": "failed"})
    await admin.patch(f"/api/v1/attempts/{a1['id']}/steps/2", json={"result": "passed"})
    a1 = (await admin.post(f"/api/v1/attempts/{a1['id']}/complete", json={})).json()

    r = await admin.post(f"/api/v1/cycle-tests/{ct_id}/retest")
    assert r.status_code == 200
    cts = (await admin.get(f"/api/v1/cycles/{cyc['id']}/tests")).json()["items"]
    assert cts[0]["displayed_result"] == "RETEST_PENDING"

    a2 = (await admin.post(f"/api/v1/cycle-tests/{ct_id}/attempts")).json()
    for i in (1, 2):
        await admin.patch(f"/api/v1/attempts/{a2['id']}/steps/{i}", json={"result": "passed"})
    a2 = (await admin.post(f"/api/v1/attempts/{a2['id']}/complete", json={})).json()

    old = (await admin.get(f"/api/v1/attempts/{a1['id']}")).json()
    assert old["overall_result"] == "FAILED"  # earlier attempt unchanged
    cts = (await admin.get(f"/api/v1/cycles/{cyc['id']}/tests")).json()["items"]
    assert cts[0]["displayed_result"] == "PASSED"
    assert cts[0]["attempt_count"] == 2


@pytest.mark.asyncio
async def test_cannot_complete_cycle_with_in_progress_attempt(admin, project):
    _, cyc, ct_id = await _ready_cycle_test(admin, project)
    await admin.post(f"/api/v1/cycle-tests/{ct_id}/attempts")
    cyc_now = [c for c in (await admin.get(f"/api/v1/projects/{project['id']}/cycles")).json() if c["id"] == cyc["id"]][0]
    r = await admin.post(
        f"/api/v1/cycles/{cyc['id']}/transitions",
        json={"to": "completed", "expected_version": cyc_now["version"]},
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_cycle_activation_requires_approved_version(admin, project):
    r = await admin.post(
        f"/api/v1/projects/{project['id']}/test-cases",
        json={"title": "unapproved", "steps": [{"action": "a", "expected_result": "b"}]},
    )
    tc = r.json()
    plan = (await admin.post(f"/api/v1/projects/{project['id']}/plans", json={"name": "P"})).json()
    await admin.post(f"/api/v1/plans/{plan['id']}/scope", json={"test_case_ids": [tc["id"]]})
    cyc = (await admin.post(
        f"/api/v1/plans/{plan['id']}/cycles", json={"name": "C", "environment": "e", "build": "b"}
    )).json()
    await admin.post(f"/api/v1/cycles/{cyc['id']}/tests", json={"test_case_ids": [tc["id"]]})
    r = await admin.post(
        f"/api/v1/cycles/{cyc['id']}/transitions",
        json={"to": "active", "expected_version": cyc["version"]},
    )
    assert r.status_code == 422
    assert "MISSING_APPROVED_VERSION" in r.text
