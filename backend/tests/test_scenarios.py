"""Requirement -> Scenario -> Test Case flow, and coverage through scenarios."""

import pytest

from tests.test_acceptance import _activate_requirement, _make_active_test_case


@pytest.fixture
def steps2():
    return [{"action": "s1", "expected_result": "e1"}, {"action": "s2", "expected_result": "e2"}]


@pytest.mark.asyncio
async def test_scenario_crud_and_test_case_assignment(admin, project, steps2):
    pid = project["id"]
    req = await _activate_requirement(admin, project, "Users can pay", None)

    r = await admin.post(
        f"/api/v1/projects/{pid}/scenarios",
        json={"title": "Pay with a saved card", "requirement_id": req["id"]},
    )
    assert r.status_code == 201, r.text
    scn = r.json()
    assert scn["key"].startswith("DEMO-SCN-")
    assert scn["requirement_id"] == req["id"]

    tc = await _make_active_test_case(admin, project, "happy path", steps2)
    r = await admin.post("/api/v1/scenarios/assign-test-case",
                         json={"test_case_id": tc["id"], "scenario_id": scn["id"]})
    assert r.status_code == 200

    listed = (await admin.get(f"/api/v1/scenarios/{scn['id']}/test-cases")).json()["items"]
    assert [t["key"] for t in listed] == [tc["key"]]

    # test cases filter by scenario
    r = await admin.get(f"/api/v1/projects/{pid}/test-cases", params={"scenario_id": scn["id"]})
    assert [i["key"] for i in r.json()["items"]] == [tc["key"]]

    # scenario list shows the test count
    s = (await admin.get(f"/api/v1/projects/{pid}/scenarios")).json()["items"][0]
    assert s["test_count"] == 1

    # edit
    r = await admin.patch(f"/api/v1/scenarios/{scn['id']}",
                          json={"expected_version": scn["version"], "title": "Pay with saved card — v2"})
    assert r.status_code == 200
    scn = r.json()
    assert scn["title"] == "Pay with saved card — v2"

    # archive
    r = await admin.post(f"/api/v1/scenarios/{scn['id']}/status",
                         json={"expected_version": scn["version"], "status": "archived"})
    assert r.status_code == 200

    # unassign
    r = await admin.post("/api/v1/scenarios/assign-test-case",
                         json={"test_case_id": tc["id"], "scenario_id": None})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_coverage_resolves_through_scenarios(admin, project, steps2):
    pid = project["id"]
    req = await _activate_requirement(admin, project, "covered via scenario", None)
    tc = await _make_active_test_case(admin, project, "the test", steps2)

    # no direct link — only a scenario under the requirement containing the test
    scn = (await admin.post(f"/api/v1/projects/{pid}/scenarios",
                            json={"title": "S", "requirement_id": req["id"]})).json()
    await admin.post("/api/v1/scenarios/assign-test-case",
                     json={"test_case_id": tc["id"], "scenario_id": scn["id"]})

    summary = (await admin.get(f"/api/v1/projects/{pid}/reports/summary")).json()
    m = {row["metric_id"]: row for row in summary["metrics"]}
    assert m["M-05"]["display"] == "100.0%"   # design coverage via the scenario
    assert m["M-09"]["value"] == 0            # nothing uncovered

    # archiving the scenario drops the coverage
    scn = (await admin.get(f"/api/v1/scenarios/{scn['id']}")).json()
    await admin.post(f"/api/v1/scenarios/{scn['id']}/status",
                     json={"expected_version": scn["version"], "status": "archived"})
    summary = (await admin.get(f"/api/v1/projects/{pid}/reports/summary")).json()
    m = {row["metric_id"]: row for row in summary["metrics"]}
    assert m["M-05"]["display"] == "0.0%"
