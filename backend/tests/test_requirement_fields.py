"""Tester feedback SUG-001..003: full requirement field set on create + edit."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_create_requirement_with_full_fields(admin, project, make_user):
    pid = project["id"]
    owner = await make_user("reqowner")
    await admin.post(f"/api/v1/projects/{pid}/members", json={"user_id": owner.user_id, "role": "tester"})

    r = await admin.post(
        f"/api/v1/projects/{pid}/requirements",
        json={
            "title": "Card vault encrypts at rest",
            "description": "All PANs stored in the vault are encrypted with AES-256.",
            "acceptance_criteria": "Given a stored card, when the DB row is read directly, the PAN is ciphertext.",
            "priority": "critical",
            "status": "active",
            "req_type": "security",
            "component": "vault-service",
            "labels": "pci, security, must-have",
            "owner_id": owner.user_id,
            "source_type": "confluence",
            "external_reference": "https://conf/x/PCI-12",
        },
    )
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["description"].startswith("All PANs")
    assert d["acceptance_criteria"].startswith("Given a stored card")
    assert d["priority"] == "critical"
    assert d["status"] == "active"
    assert d["req_type"] == "security"
    assert d["component"] == "vault-service"
    assert d["labels"] == "pci, security, must-have"
    assert d["owner_id"] == owner.user_id
    assert d["owner_name"] == "Reqowner"
    assert d["source_type"] == "confluence"
    assert d["external_reference"] == "https://conf/x/PCI-12"


async def test_edit_requirement_all_fields_and_release(admin, project):
    pid = project["id"]
    rel = (await admin.post(f"/api/v1/projects/{pid}/releases", json={"name": "R1"})).json()
    r = (await admin.post(f"/api/v1/projects/{pid}/requirements", json={"title": "Draft req"})).json()

    upd = await admin.patch(
        f"/api/v1/requirements/{r['id']}",
        json={
            "expected_version": r["version"],
            "description": "now has a description",
            "acceptance_criteria": "AC added",
            "status": "active",
            "labels": "backend",
            "release_id": rel["id"],
        },
    )
    assert upd.status_code == 200, upd.text
    d = upd.json()
    assert d["description"] == "now has a description"
    assert d["acceptance_criteria"] == "AC added"
    assert d["status"] == "active"
    assert d["labels"] == "backend"
    assert d["release_id"] == rel["id"]

    # release is editable — move it back off the release
    d2 = await admin.patch(
        f"/api/v1/requirements/{r['id']}",
        json={"expected_version": d["version"], "clear_release": True},
    )
    assert d2.status_code == 200
    assert d2.json()["release_id"] is None


async def test_requirement_history_visible(admin, project):
    pid = project["id"]
    r = (await admin.post(f"/api/v1/projects/{pid}/requirements", json={"title": "Trace me"})).json()
    await admin.patch(f"/api/v1/requirements/{r['id']}", json={"expected_version": r["version"], "title": "Trace me v2"})

    h = await admin.get(f"/api/v1/requirements/{r['id']}/history")
    assert h.status_code == 200, h.text
    actions = [it["action"] for it in h.json()["items"]]
    assert "requirement.created" in actions
    assert "requirement.updated" in actions


async def test_owner_must_be_project_member(admin, project, make_user):
    pid = project["id"]
    stranger = await make_user("notamember")
    r = await admin.post(
        f"/api/v1/projects/{pid}/requirements",
        json={"title": "x", "owner_id": stranger.user_id},
    )
    assert r.status_code in (400, 422)
