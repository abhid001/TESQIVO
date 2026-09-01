"""Notification inbox: feedback + access requests reach admins; mark read."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_feedback_notifies_system_admin(admin, make_user):
    member = await make_user("nora")
    assert (await admin.get("/api/v1/notifications")).json()["unread"] == 0

    r = await member.post("/api/v1/feedback", json={"message": "the donut is off-centre", "category": "bug"})
    assert r.status_code == 201

    n = (await admin.get("/api/v1/notifications")).json()
    assert n["unread"] == 1
    top = n["items"][0]
    assert top["kind"] == "feedback"
    assert "nora" in top["title"].lower()
    assert top["link"] == "/admin/feedback"
    assert top["read"] is False

    # mark it read
    assert (await admin.post(f"/api/v1/notifications/{top['id']}/read")).status_code == 204
    n2 = (await admin.get("/api/v1/notifications")).json()
    assert n2["unread"] == 0
    assert n2["items"][0]["read"] is True

    # the member sees none of it
    assert (await member.get("/api/v1/notifications")).json()["unread"] == 0


async def test_access_request_notifies_admins_and_read_all(admin, make_user, project):
    stranger = await make_user("percy")
    await stranger.post(f"/api/v1/projects/{project['id']}/access-requests", json={"requested_role": "tester"})

    n = (await admin.get("/api/v1/notifications")).json()
    assert any(it["kind"] == "access_request" and "percy" in it["title"].lower() for it in n["items"])

    assert (await admin.post("/api/v1/notifications/read-all")).status_code == 204
    assert (await admin.get("/api/v1/notifications")).json()["unread"] == 0


async def test_cannot_read_another_users_notification(admin, make_user):
    other = await make_user("quinn")
    await other.post("/api/v1/feedback", json={"message": "x", "category": "idea"})
    nid = (await admin.get("/api/v1/notifications")).json()["items"][0]["id"]
    assert (await other.post(f"/api/v1/notifications/{nid}/read")).status_code == 404
