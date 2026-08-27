"""Increments 4-5: repository, versioning, workflow, immutable history."""

import pytest


async def _tc(admin, project, title="Checkout flow"):
    r = await admin.post(
        f"/api/v1/projects/{project['id']}/test-cases",
        json={
            "title": title,
            "description": "d",
            "steps": [
                {"action": "add item", "expected_result": "cart shows item"},
                {"action": "pay", "expected_result": "order confirmed"},
            ],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _approve_activate(admin, tc):
    for to in ("in_review", "approved"):
        r = await admin.post(
            f"/api/v1/test-cases/{tc['id']}/version-transitions",
            json={"to": to, "expected_version": tc["version"]},
        )
        assert r.status_code == 200, r.text
        tc = r.json()
    r = await admin.post(
        f"/api/v1/test-cases/{tc['id']}/lifecycle-transitions",
        json={"to": "active", "expected_version": tc["version"]},
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_key_is_project_scoped_and_sequential(admin, project):
    a = await _tc(admin, project, "A")
    b = await _tc(admin, project, "B")
    assert a["key"] == "DEMO-TC-1"
    assert b["key"] == "DEMO-TC-2"


@pytest.mark.asyncio
async def test_cannot_submit_for_review_without_steps(admin, project):
    r = await admin.post(
        f"/api/v1/projects/{project['id']}/test-cases", json={"title": "no steps"}
    )
    tc = r.json()
    r = await admin.post(
        f"/api/v1/test-cases/{tc['id']}/version-transitions",
        json={"to": "in_review", "expected_version": tc["version"]},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_controlled_edit_after_approval_forks_new_draft_version(admin, project):
    tc = await _tc(admin, project)
    tc = await _approve_activate(admin, tc)
    assert tc["lifecycle_state"] == "active"
    approved_vid = tc["approved_version_id"]

    r = await admin.patch(
        f"/api/v1/test-cases/{tc['id']}",
        json={"expected_version": tc["version"], "title": "Checkout flow v2", "change_summary": "reword"},
    )
    assert r.status_code == 200, r.text
    tc2 = r.json()
    assert tc2["has_draft_changes"] is True
    assert tc2["approved_version_id"] == approved_vid  # unchanged - still used by cycles
    assert tc2["current_version_id"] != approved_vid

    r = await admin.get(f"/api/v1/test-cases/{tc['id']}/versions")
    versions = r.json()
    assert [v["version_number"] for v in versions] == [1, 2]
    assert versions[0]["status"] == "approved"  # v1 still approved & immutable
    assert versions[1]["status"] == "draft"


@pytest.mark.asyncio
async def test_invalid_transition_returns_409(admin, project):
    tc = await _tc(admin, project)
    r = await admin.post(
        f"/api/v1/test-cases/{tc['id']}/lifecycle-transitions",
        json={"to": "active", "expected_version": tc["version"]},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "STATE_TRANSITION_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_optimistic_concurrency_conflict(admin, project):
    tc = await _tc(admin, project)
    r = await admin.patch(
        f"/api/v1/test-cases/{tc['id']}",
        json={"expected_version": 999, "title": "x"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "VERSION_CONFLICT"
