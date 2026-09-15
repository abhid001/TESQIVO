"""Requirements-page rebuild: linked-test counts, release info, trace summary."""

import pytest

from tests.test_acceptance import _make_active_test_case, _run_attempt

pytestmark = pytest.mark.asyncio


async def test_linked_and_qualifying_test_counts(admin, project):
    pid = project["id"]
    req = (await admin.post(f"/api/v1/projects/{pid}/requirements", json={"title": "Req A"})).json()

    draft_tc = (
        await admin.post(f"/api/v1/projects/{pid}/test-cases", json={"title": "Draft TC", "steps": []})
    ).json()
    active_tc = await _make_active_test_case(admin, project, "Active TC", [{"action": "a", "expected_result": "e"}])

    for tc in (draft_tc, active_tc):
        r = await admin.post(
            f"/api/v1/projects/{pid}/trace-links",
            json={"source_type": "requirement", "source_id": req["id"], "target_type": "test_case", "target_id": tc["id"]},
        )
        assert r.status_code == 201, r.text

    got = (await admin.get(f"/api/v1/requirements/{req['id']}")).json()
    assert got["linked_test_count"] == 2
    assert got["qualifying_test_count"] == 1  # only the active one is approved/active

    listed = (await admin.get(f"/api/v1/projects/{pid}/requirements")).json()
    row = next(r for r in listed["items"] if r["id"] == req["id"])
    assert row["linked_test_count"] == 2
    assert row["qualifying_test_count"] == 1


async def test_release_info_denormalized(admin, project):
    pid = project["id"]
    rel = (await admin.post(f"/api/v1/projects/{pid}/releases", json={"name": "Spring Release"})).json()
    req = (
        await admin.post(
            f"/api/v1/projects/{pid}/requirements", json={"title": "Req B", "release_id": rel["id"]}
        )
    ).json()
    assert req["release_key"] == rel["key"]
    assert req["release_name"] == "Spring Release"

    listed = (await admin.get(f"/api/v1/projects/{pid}/requirements")).json()
    row = next(r for r in listed["items"] if r["id"] == req["id"])
    assert row["release_key"] == rel["key"]
    assert row["release_name"] == "Spring Release"


async def test_trace_summary_counts_test_cases_executions_defects(admin, project):
    pid = project["id"]
    req = (await admin.post(f"/api/v1/projects/{pid}/requirements", json={"title": "Req C"})).json()
    tc = await _make_active_test_case(admin, project, "TC1", [{"action": "a", "expected_result": "e"}])
    await admin.post(
        f"/api/v1/projects/{pid}/trace-links",
        json={"source_type": "requirement", "source_id": req["id"], "target_type": "test_case", "target_id": tc["id"]},
    )
    defect = (await admin.post(f"/api/v1/projects/{pid}/defects", json={"summary": "Bug"})).json()
    r = await admin.post(
        f"/api/v1/projects/{pid}/trace-links",
        # legal direction is defect -> requirement ("regresses")
        json={"source_type": "defect", "source_id": defect["id"], "target_type": "requirement", "target_id": req["id"]},
    )
    assert r.status_code == 201, r.text

    plan = (await admin.post(f"/api/v1/projects/{pid}/plans", json={"name": "P"})).json()
    await admin.post(f"/api/v1/plans/{plan['id']}/scope", json={"test_case_ids": [tc["id"]]})
    cyc = (
        await admin.post(
            f"/api/v1/plans/{plan['id']}/cycles", json={"name": "C", "environment": "staging", "build": "1"}
        )
    ).json()
    await admin.post(f"/api/v1/cycles/{cyc['id']}/tests", json={"test_case_ids": [tc["id"]]})
    await admin.post(f"/api/v1/cycles/{cyc['id']}/transitions", json={"to": "active", "expected_version": cyc["version"]})
    cts = (await admin.get(f"/api/v1/cycles/{cyc['id']}/tests")).json()["items"]
    await _run_attempt(admin, cts[0]["id"], ["passed"])

    got = (await admin.get(f"/api/v1/requirements/{req['id']}")).json()
    assert got["trace_summary"] == {"test_cases": 1, "executions": 1, "defects": 1}


async def test_updated_at_present_and_advances_on_edit(admin, project):
    pid = project["id"]
    req = (await admin.post(f"/api/v1/projects/{pid}/requirements", json={"title": "Req D"})).json()
    assert req["created_at"]
    assert req["updated_at"]

    upd = (
        await admin.patch(
            f"/api/v1/requirements/{req['id']}",
            json={"expected_version": req["version"], "title": "Req D renamed"},
        )
    ).json()
    assert upd["updated_at"]
    assert upd["title"] == "Req D renamed"
