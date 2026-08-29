"""Environment (and other) reference values — add / list / delete from admin."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_admin_manages_environments(admin, project):
    pid = project["id"]
    # seeded defaults
    r = await admin.get(f"/api/v1/projects/{pid}/reference-values")
    envs = [x for x in r.json() if x["kind"] == "environment"]
    assert {e["value"] for e in envs} == {"development", "staging", "production"}

    add = await admin.post(
        f"/api/v1/projects/{pid}/reference-values",
        json={"kind": "environment", "value": "pre-production"},
    )
    assert add.status_code == 201, add.text
    ref_id = add.json()["id"]

    envs = [x for x in (await admin.get(f"/api/v1/projects/{pid}/reference-values")).json() if x["kind"] == "environment"]
    assert "pre-production" in {e["value"] for e in envs}

    d = await admin.delete(f"/api/v1/projects/{pid}/reference-values/{ref_id}")
    assert d.status_code == 204
    envs = [x for x in (await admin.get(f"/api/v1/projects/{pid}/reference-values")).json() if x["kind"] == "environment"]
    assert "pre-production" not in {e["value"] for e in envs}


async def test_non_member_cannot_delete_reference_value(admin, make_user, project):
    pid = project["id"]
    ref_id = (await admin.get(f"/api/v1/projects/{pid}/reference-values")).json()[0]["id"]
    stranger = await make_user("olive")
    d = await stranger.delete(f"/api/v1/projects/{pid}/reference-values/{ref_id}")
    assert d.status_code in (403, 404)
