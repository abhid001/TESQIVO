"""Feedback triage + project discovery / access requests (increment: self-service)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_any_user_can_submit_feedback_and_admin_triages(admin, make_user, project):
    member = await make_user("frank")

    r = await member.post(
        "/api/v1/feedback",
        json={"message": "The cycles page scrolls oddly", "category": "bug", "project_id": project["id"], "page_path": "/p/DEMO/cycles"},
    )
    assert r.status_code == 201, r.text

    # member cannot list feedback
    assert (await member.get("/api/v1/feedback")).status_code == 403

    rows = (await admin.get("/api/v1/feedback")).json()
    assert len(rows) == 1
    fb = rows[0]
    assert fb["category"] == "bug"
    assert fb["user_username"] == "frank"
    assert fb["project_key"] == "DEMO"
    assert fb["status"] == "open"

    upd = await admin.patch(f"/api/v1/feedback/{fb['id']}", json={"status": "resolved", "admin_note": "fixed in build 12"})
    assert upd.status_code == 200, upd.text
    assert upd.json()["status"] == "resolved"
    assert upd.json()["resolved_at"] is not None

    csv = await admin.get("/api/v1/feedback/export?format=csv")
    assert csv.status_code == 200
    assert "frank@example.com" in csv.text
    assert "fixed in build 12" in csv.text

    txt = await admin.get("/api/v1/feedback/export?format=txt")
    assert "BUG" in txt.text


async def test_empty_feedback_rejected(make_user):
    member = await make_user("gina")
    r = await member.post("/api/v1/feedback", json={"message": "   "})
    assert r.status_code == 422 or r.status_code == 400


async def test_discover_projects_and_request_access_flow(admin, make_user, project):
    member = await make_user("harry")

    disc = (await member.get("/api/v1/projects/discoverable")).json()
    assert len(disc) == 1
    assert disc[0]["key"] == "DEMO"
    assert disc[0]["is_member"] is False
    assert disc[0]["pending_request_role"] is None

    req = await member.post(
        f"/api/v1/projects/{project['id']}/access-requests",
        json={"requested_role": "tester", "message": "please add me"},
    )
    assert req.status_code == 201, req.text

    # now shows pending
    disc = (await member.get("/api/v1/projects/discoverable")).json()
    assert disc[0]["pending_request_role"] == "tester"

    # admin sees it and approves
    pending = (await admin.get("/api/v1/access-requests")).json()
    assert len(pending) == 1
    assert pending[0]["username"] == "harry"

    decided = await admin.post(
        f"/api/v1/access-requests/{pending[0]['id']}/decide", json={"approve": True, "role": "test_manager"}
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "approved"

    # harry now a member
    projs = (await member.get("/api/v1/projects")).json()
    assert [p["key"] for p in projs] == ["DEMO"]

    # no more pending
    assert (await admin.get("/api/v1/access-requests")).json() == []


async def test_project_admin_sees_only_their_requests(admin, make_user, project):
    p2 = (await admin.post("/api/v1/projects", json={"key": "OTHER", "name": "Other"})).json()
    ivy = await make_user("ivy")
    await admin.post(
        f"/api/v1/projects/{p2['id']}/members", json={"user_id": ivy.user_id, "role": "project_admin"}
    )

    stranger = await make_user("jack")
    await stranger.post(f"/api/v1/projects/{project['id']}/access-requests", json={"requested_role": "tester"})
    await stranger.post(f"/api/v1/projects/{p2['id']}/access-requests", json={"requested_role": "tester"})

    # the actor's memberships are reloaded per-request, so ivy sees OTHER's request only
    seen = (await ivy.get("/api/v1/access-requests")).json()
    assert {r["project_key"] for r in seen} == {"OTHER"}


async def test_admin_lists_user_memberships(admin, make_user, project):
    u = await make_user("kate")
    await admin.post(f"/api/v1/projects/{project['id']}/members", json={"user_id": u.user_id, "role": "tester"})
    rows = (await admin.get(f"/api/v1/users/{u.user_id}/memberships")).json()
    assert rows == [{"project_id": project["id"], "project_key": "DEMO", "project_name": "Demo Project", "role": "tester"}]
