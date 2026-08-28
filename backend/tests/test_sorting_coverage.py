"""Alphanumeric default ordering, sort= param, pagination meta, coverage-by-type."""

import pytest


async def _bulk_requirements(admin, pid, n):
    for i in range(1, n + 1):
        await admin.post(f"/api/v1/projects/{pid}/requirements", json={"title": f"req {i}"})


@pytest.mark.asyncio
async def test_default_order_is_natural_alphanumeric(admin, project):
    pid = project["id"]
    await _bulk_requirements(admin, pid, 12)
    r = await admin.get(f"/api/v1/projects/{pid}/requirements", params={"page_size": 200})
    keys = [x["key"] for x in r.json()["items"]]
    # natural: DEMO-REQ-2 before DEMO-REQ-10 (lexical would put -10 first)
    assert keys == [f"DEMO-REQ-{i}" for i in range(1, 13)]


@pytest.mark.asyncio
async def test_sort_param_and_pagination_meta(admin, project):
    pid = project["id"]
    for name in ["Zeta", "alpha", "Mike"]:
        await admin.post(f"/api/v1/projects/{pid}/requirements", json={"title": name})
    r = await admin.get(f"/api/v1/projects/{pid}/requirements", params={"sort": "title"})
    titles = [x["title"] for x in r.json()["items"]]
    assert titles == ["alpha", "Mike", "Zeta"]

    r = await admin.get(f"/api/v1/projects/{pid}/requirements", params={"sort": "-title"})
    assert [x["title"] for x in r.json()["items"]] == ["Zeta", "Mike", "alpha"]

    r = await admin.get(f"/api/v1/projects/{pid}/requirements", params={"page": 1, "page_size": 2})
    body = r.json()
    assert body["page"] == 1 and body["page_size"] == 2 and body["total"] == 3 and body["pages"] == 2

    r = await admin.get(f"/api/v1/projects/{pid}/requirements", params={"sort": "not_a_field"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_test_case_sort_and_pages(admin, project):
    pid = project["id"]
    for i in range(1, 6):
        await admin.post(
            f"/api/v1/projects/{pid}/test-cases",
            json={"title": f"case {i}", "steps": [{"action": "a", "expected_result": "b"}]},
        )
    r = await admin.get(f"/api/v1/projects/{pid}/test-cases", params={"page_size": 2})
    b = r.json()
    assert b["pages"] == 3 and b["total"] == 5
    r = await admin.get(f"/api/v1/projects/{pid}/test-cases", params={"sort": "-title", "page_size": 50})
    assert [i["title"] for i in r.json()["items"]][0] == "case 5"


@pytest.mark.asyncio
async def test_coverage_by_type(admin, project):
    pid = project["id"]

    async def make_tc(title, automation):
        r = await admin.post(
            f"/api/v1/projects/{pid}/test-cases",
            json={"title": title, "automation_status": automation,
                  "steps": [{"action": "a", "expected_result": "b"}]},
        )
        tc = r.json()
        for to in ("in_review", "approved"):
            tc = (await admin.post(f"/api/v1/test-cases/{tc['id']}/version-transitions",
                                   json={"to": to, "expected_version": tc["version"]})).json()
        tc = (await admin.post(f"/api/v1/test-cases/{tc['id']}/lifecycle-transitions",
                               json={"to": "active", "expected_version": tc["version"]})).json()
        return tc

    auto = await make_tc("automated one", "automated")
    manual = await make_tc("manual one", "candidate")

    req = (await admin.post(f"/api/v1/projects/{pid}/requirements", json={"title": "r"})).json()
    req = (await admin.post(f"/api/v1/requirements/{req['id']}/transitions",
                            json={"to": "active", "expected_version": req["version"]})).json()
    for tc in (auto, manual):
        await admin.post(f"/api/v1/projects/{pid}/trace-links", json={
            "source_type": "requirement", "source_id": req["id"],
            "target_type": "test_case", "target_id": tc["id"]})

    r = await admin.get(f"/api/v1/projects/{pid}/reports/coverage-by-type")
    assert r.status_code == 200
    body = r.json()
    assert body["tests"]["automated"] == 1
    assert body["tests"]["manual"] == 1
    assert body["requirement_coverage"]["covered_by_automated"] == 1
    assert body["requirement_coverage"]["covered_by_manual"] == 1
