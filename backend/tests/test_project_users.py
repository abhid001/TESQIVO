"""Project-wise user management: a project admin provisions members who can then
work in the test management tool."""

import pytest


@pytest.mark.asyncio
async def test_project_admin_provisions_a_member_who_can_author(project, admin, make_user):
    pid = project["id"]

    # promote a plain user to project_admin
    padmin = await make_user("padmin")
    r = await admin.post(f"/api/v1/projects/{pid}/members", json={"user_id": padmin.user_id, "role": "project_admin"})
    assert r.status_code == 201

    # the project admin creates a brand-new member with the test_manager role
    r = await padmin.post(
        f"/api/v1/projects/{pid}/members",
        json={
            "role": "test_manager",
            "new_user": {
                "username": "qa_lee",
                "email": "lee@example.com",
                "display_name": "QA Lee",
                "password": "LeeStrongPass1!",
            },
        },
    )
    assert r.status_code == 201, r.text

    members = (await admin.get(f"/api/v1/projects/{pid}/members")).json()
    assert any(m["username"] == "qa_lee" and m["role"] == "test_manager" for m in members)


@pytest.mark.asyncio
async def test_project_admin_cannot_create_system_admins(project, admin, make_user):
    pid = project["id"]
    padmin = await make_user("padmin2")
    await admin.post(f"/api/v1/projects/{pid}/members", json={"user_id": padmin.user_id, "role": "project_admin"})

    r = await padmin.post(
        f"/api/v1/projects/{pid}/members",
        json={
            "role": "test_manager",
            "new_user": {
                "username": "sneaky", "email": "s@example.com",
                "display_name": "S", "password": "SneakyPass123!",
            },
        },
    )
    assert r.status_code == 201
    users = (await admin.get("/api/v1/users")).json()
    created = next(u for u in users if u["username"] == "sneaky")
    assert created["is_system_admin"] is False


@pytest.mark.asyncio
async def test_new_member_can_author_and_execute(client, project, admin, make_user):
    pid = project["id"]
    padmin = await make_user("padmin3")
    await admin.post(f"/api/v1/projects/{pid}/members", json={"user_id": padmin.user_id, "role": "project_admin"})
    r = await padmin.post(
        f"/api/v1/projects/{pid}/members",
        json={
            "role": "test_manager",
            "new_user": {
                "username": "worker1", "email": "w1@example.com",
                "display_name": "Worker One", "password": "WorkerPass123!",
            },
        },
    )
    assert r.status_code == 201

    # sign the new member in on a fresh cookie jar and let them create a test case + release
    await client.post("/api/v1/auth/session", json={"username": "worker1", "password": "WorkerPass123!"})
    csrf = client.cookies.get("tesqivo_csrf")
    h = {"X-CSRF-Token": csrf, "X-Tesqivo-Client": "web"}
    r = await client.post(f"/api/v1/projects/{pid}/test-cases",
                          json={"title": "Worker TC", "steps": [{"action": "a", "expected_result": "b"}]}, headers=h)
    assert r.status_code == 201
    r = await client.post(f"/api/v1/projects/{pid}/releases", json={"name": "R by worker"}, headers=h)
    assert r.status_code == 201
