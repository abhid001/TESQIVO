"""Project audit log: admin/test_manager only, paginated, real user actions visible."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_only_admin_and_test_manager_can_view_audit_log(project, admin, make_user):
    pid = project["id"]
    test_manager = await make_user("tm1")
    tester = await make_user("tester_audit")
    viewer = await make_user("viewer_audit")
    for user, role in ((test_manager, "test_manager"), (tester, "tester"), (viewer, "viewer")):
        r = await admin.post(f"/api/v1/projects/{pid}/members", json={"user_id": user.user_id, "role": role})
        assert r.status_code == 201, r.text

    r = await admin.get(f"/api/v1/projects/{pid}/audit-log")
    assert r.status_code == 200, r.text

    r = await test_manager.get(f"/api/v1/projects/{pid}/audit-log")
    assert r.status_code == 200, r.text

    r = await tester.get(f"/api/v1/projects/{pid}/audit-log")
    assert r.status_code == 403, r.text

    r = await viewer.get(f"/api/v1/projects/{pid}/audit-log")
    assert r.status_code == 403, r.text


async def test_non_member_cannot_view_audit_log(project, make_user):
    outsider = await make_user("outsider_audit")
    r = await outsider.get(f"/api/v1/projects/{project['id']}/audit-log")
    assert r.status_code == 404  # existence not disclosed (D-010)


async def test_audit_log_records_real_actions_and_paginates(admin, project):
    pid = project["id"]
    for i in range(3):
        r = await admin.post(f"/api/v1/projects/{pid}/requirements", json={"title": f"Req {i}"})
        assert r.status_code == 201, r.text

    r = await admin.get(f"/api/v1/projects/{pid}/audit-log", params={"entity_type": "requirement", "page_size": 2})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 3
    assert len(body["items"]) == 2
    row = body["items"][0]
    assert row["entity_type"] == "requirement"
    assert row["action"] == "requirement.created"
    assert row["actor"]  # display name resolved
    assert "at" in row


async def test_audit_log_filters_by_entity_type(admin, project):
    pid = project["id"]
    await admin.post(f"/api/v1/projects/{pid}/requirements", json={"title": "Filter me"})
    await admin.post(f"/api/v1/projects/{pid}/defects", json={"summary": "A bug"})

    r = await admin.get(f"/api/v1/projects/{pid}/audit-log", params={"entity_type": "defect"})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items
    assert all(it["entity_type"] == "defect" for it in items)
