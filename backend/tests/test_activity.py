"""Recent-activity feed for the dashboard."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_activity_feed_lists_recent_project_events(admin, project):
    pid = project["id"]
    await admin.post(f"/api/v1/projects/{pid}/requirements", json={"title": "Login works"})
    await admin.post(f"/api/v1/projects/{pid}/releases", json={"name": "R1"})

    r = await admin.get(f"/api/v1/projects/{pid}/activity")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) >= 3  # project.created + requirement.created + release.created
    assert all(set(it) == {"id", "action", "text", "actor", "kind", "at"} for it in items)
    actions = {it["action"] for it in items}
    assert {"project.created", "requirement.created", "release.created"} <= actions
    rel = next(it for it in items if it["action"] == "release.created")
    assert "Release" in rel["text"] and "created" in rel["text"]
    assert rel["actor"] == "Admin"


async def test_activity_feed_requires_membership(make_user, project):
    stranger = await make_user("nate")
    r = await stranger.get(f"/api/v1/projects/{project['id']}/activity")
    assert r.status_code == 404
