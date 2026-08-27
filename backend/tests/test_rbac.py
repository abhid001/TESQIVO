"""Increment 3: project RBAC - permitted vs forbidden, non-member isolation (§19.2)."""

import pytest


@pytest.mark.asyncio
async def test_non_member_cannot_see_project_via_api(project, make_user):
    outsider = await make_user("outsider")
    r = await outsider.get(f"/api/v1/projects/{project['id']}")
    assert r.status_code == 404  # existence not disclosed (decision D-010)
    r = await outsider.get(f"/api/v1/projects/{project['id']}/test-cases")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_viewer_cannot_create_test_case_but_can_read(project, admin, make_user):
    viewer = await make_user("viewer1")
    r = await admin.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": viewer.user_id, "role": "viewer"},
    )
    assert r.status_code == 201

    r = await viewer.get(f"/api/v1/projects/{project['id']}/test-cases")
    assert r.status_code == 200

    r = await viewer.post(
        f"/api/v1/projects/{project['id']}/test-cases",
        json={"title": "T", "steps": [{"action": "a", "expected_result": "b"}]},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_tester_cannot_author_or_approve_test_cases(project, admin, make_user):
    tester = await make_user("tester3")
    await admin.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": tester.user_id, "role": "tester"},
    )
    # authoring the repository is a Test Manager responsibility (PRS §10)
    r = await tester.post(
        f"/api/v1/projects/{project['id']}/test-cases",
        json={"title": "Login works", "steps": [{"action": "open", "expected_result": "form"}]},
    )
    assert r.status_code == 403

    # but a tester CAN create requirements and defects
    r = await tester.post(
        f"/api/v1/projects/{project['id']}/requirements", json={"title": "Users can log in"}
    )
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_only_system_admin_creates_projects(make_user):
    manager = await make_user("pm1")
    r = await manager.post("/api/v1/projects", json={"key": "NOPE", "name": "x"})
    assert r.status_code == 403
