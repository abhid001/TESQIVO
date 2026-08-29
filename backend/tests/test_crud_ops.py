"""Edit + delete for requirements, plans, users, projects; execution-trend."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_requirement_edit_and_delete(admin, project):
    pid = project["id"]
    r = (await admin.post(f"/api/v1/projects/{pid}/requirements", json={"title": "Old title", "priority": "low"})).json()

    upd = await admin.patch(
        f"/api/v1/requirements/{r['id']}",
        json={"expected_version": r["version"], "title": "New title", "priority": "high"},
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["title"] == "New title"
    assert upd.json()["priority"] == "high"

    d = await admin.delete(f"/api/v1/requirements/{r['id']}")
    assert d.status_code == 204
    rows = (await admin.get(f"/api/v1/projects/{pid}/requirements")).json()["items"]
    assert r["id"] not in {x["id"] for x in rows}


async def test_plan_edit_and_delete(admin, project):
    pid = project["id"]
    p = (await admin.post(f"/api/v1/projects/{pid}/plans", json={"name": "Sprint plan"})).json()

    upd = await admin.patch(f"/api/v1/plans/{p['id']}", json={"expected_version": p["version"], "name": "Renamed plan"})
    assert upd.status_code == 200, upd.text
    assert upd.json()["name"] == "Renamed plan"

    d = await admin.delete(f"/api/v1/plans/{p['id']}")
    assert d.status_code == 204
    assert (await admin.get(f"/api/v1/projects/{pid}/plans")).json() == []


async def test_user_edit_and_delete_guard(admin, make_user):
    fresh = await make_user("zoe")
    upd = await admin.patch(f"/api/v1/users/{fresh.user_id}", json={"display_name": "Zoe Q."})
    assert upd.status_code == 200, upd.text
    assert upd.json()["display_name"] == "Zoe Q."

    # no footprint -> deletable
    d = await admin.delete(f"/api/v1/users/{fresh.user_id}")
    assert d.status_code == 204
    users = (await admin.get("/api/v1/users")).json()
    assert fresh.user_id not in {u["id"] for u in users}


async def test_user_delete_blocked_when_member(admin, make_user, project):
    u = await make_user("member-user")
    await admin.post(f"/api/v1/projects/{project['id']}/members", json={"user_id": u.user_id, "role": "tester"})
    d = await admin.delete(f"/api/v1/users/{u.user_id}")
    assert d.status_code == 422 or d.status_code == 400


async def test_project_delete_requires_empty_and_archived(admin, project):
    pid = project["id"]
    # not archived -> refused
    assert (await admin.delete(f"/api/v1/projects/{pid}")).status_code in (400, 422)

    # archive then delete (empty project)
    p = (await admin.get(f"/api/v1/projects/{pid}")).json()
    await admin.post(f"/api/v1/projects/{pid}/archive", json={"expected_version": p["version"]})
    d = await admin.delete(f"/api/v1/projects/{pid}")
    assert d.status_code == 204, d.text
    assert (await admin.get("/api/v1/projects")).json() == []


async def test_project_delete_blocked_with_data(admin, project):
    pid = project["id"]
    await admin.post(f"/api/v1/projects/{pid}/requirements", json={"title": "keeps project non-empty"})
    p = (await admin.get(f"/api/v1/projects/{pid}")).json()
    await admin.post(f"/api/v1/projects/{pid}/archive", json={"expected_version": p["version"]})
    assert (await admin.delete(f"/api/v1/projects/{pid}")).status_code in (400, 422)


async def test_execution_trend_shape(admin, project):
    r = await admin.get(f"/api/v1/projects/{project['id']}/reports/execution-trend?days=14")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["days"] == 14
    assert len(body["series"]) == 14
    assert set(body["series"][0]) == {"date", "passed", "failed", "blocked", "other", "total"}
