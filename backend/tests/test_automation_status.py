"""automation_status is a non-controlled logical field - settable directly, no
version fork, no review workflow (controlled_fields.py NON_CONTROLLED_LOGICAL_FIELDS)."""

import pytest

pytestmark = pytest.mark.asyncio


async def _tc(admin, project, title="Checkout flow"):
    r = await admin.post(
        f"/api/v1/projects/{project['id']}/test-cases",
        json={"title": title, "steps": [{"action": "a", "expected_result": "e"}]},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_set_automation_status(admin, project):
    tc = await _tc(admin, project)
    assert tc["automation_status"] == "candidate"  # default

    r = await admin.post(
        f"/api/v1/test-cases/{tc['id']}/automation-status",
        json={"automation_status": "automated", "expected_version": tc["version"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["automation_status"] == "automated"
    assert body["version"] == tc["version"] + 1

    # does not fork a version - current_version_id unchanged
    assert body["current_version_id"] == tc["current_version_id"]


async def test_automation_status_does_not_require_approval(admin, project):
    """A brand-new draft test case (not reviewed/approved) can still have its
    automation status set - it's organizational metadata, not controlled content."""
    tc = await _tc(admin, project)
    assert tc["lifecycle_state"] == "draft"
    r = await admin.post(
        f"/api/v1/test-cases/{tc['id']}/automation-status",
        json={"automation_status": "not_applicable", "expected_version": tc["version"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["automation_status"] == "not_applicable"


async def test_invalid_automation_status_rejected(admin, project):
    tc = await _tc(admin, project)
    r = await admin.post(
        f"/api/v1/test-cases/{tc['id']}/automation-status",
        json={"automation_status": "bogus", "expected_version": tc["version"]},
    )
    assert r.status_code == 422, r.text


async def test_archived_test_case_automation_status_locked(admin, project):
    tc = await _tc(admin, project)
    r = await admin.post(
        f"/api/v1/test-cases/{tc['id']}/lifecycle-transitions",
        json={"to": "archived", "expected_version": tc["version"]},
    )
    assert r.status_code == 200, r.text
    tc = r.json()
    r = await admin.post(
        f"/api/v1/test-cases/{tc['id']}/automation-status",
        json={"automation_status": "automated", "expected_version": tc["version"]},
    )
    assert r.status_code == 409, r.text


async def test_automation_status_optimistic_concurrency(admin, project):
    tc = await _tc(admin, project)
    r = await admin.post(
        f"/api/v1/test-cases/{tc['id']}/automation-status",
        json={"automation_status": "automated", "expected_version": tc["version"] - 1 if tc["version"] > 1 else 99},
    )
    assert r.status_code == 409, r.text


async def test_tester_can_only_set_on_own_test_case(admin, project, make_user):
    tester = await make_user("tc_tester")
    await admin.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": tester.user_id, "role": "tester"},
    )
    # tester cannot author test cases at all (test_case.create is test_manager-only)
    r = await tester.post(
        f"/api/v1/projects/{project['id']}/test-cases",
        json={"title": "T", "steps": [{"action": "a", "expected_result": "b"}]},
    )
    assert r.status_code == 403, r.text

    # but can set automation status on one they were made co-author of via edit rights -
    # simplest check here: a test_manager-owned case is off-limits to a tester
    tc = await _tc(admin, project)
    r = await tester.post(
        f"/api/v1/test-cases/{tc['id']}/automation-status",
        json={"automation_status": "automated", "expected_version": tc["version"]},
    )
    assert r.status_code == 403, r.text
