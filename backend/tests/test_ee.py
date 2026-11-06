"""Enterprise edition wiring: version, license gate, community-has-no-EE guard."""

import pytest

from app.core import license as lic_mod


@pytest.fixture(autouse=True)
def _clear():
    lic_mod.reset_cache_for_tests()
    yield
    lic_mod.reset_cache_for_tests()


@pytest.mark.asyncio
async def test_version_reports_edition_and_features(client, issue_license):
    r = await client.get("/api/v1/version")
    body = r.json()
    assert body["edition"] == "enterprise"          # app/ee/ present in the test tree
    assert body["features"] == []                   # no license installed yet

    issue_license(features=["ai"])
    body2 = (await client.get("/api/v1/version")).json()
    assert body2["features"] == ["ai"]


@pytest.mark.asyncio
async def test_ee_feature_needs_a_license(client):
    r = await client.post(
        "/api/v1/ee/ai/draft-test-case", json={"requirement_text": "Users can reset their password"}
    )
    assert r.status_code == 402
    assert r.json()["error"]["code"] == "LICENSE_REQUIRED"


@pytest.mark.asyncio
async def test_ee_feature_works_with_a_matching_license(client, admin, issue_license):
    issue_license(features=["ai"])
    r = await admin.post(
        "/api/v1/ee/ai/draft-test-case", json={"requirement_text": "Login must lock after 5 tries"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "stub"


@pytest.mark.asyncio
async def test_ee_feature_rejected_when_license_lacks_it(client, issue_license):
    issue_license(features=["sso"])  # no "ai"
    r = await client.post(
        "/api/v1/ee/ai/draft-test-case", json={"requirement_text": "x"}
    )
    assert r.status_code == 402


@pytest.mark.asyncio
async def test_license_endpoint_is_admin_only(client, admin, make_user, issue_license):
    issue_license(features=["ai"], sub="Acme")
    ok = await admin.get("/api/v1/ee/license")
    assert ok.status_code == 200 and ok.json()["customer"] == "Acme" and ok.json()["licensed"]

    member = await make_user("plain")
    assert (await member.get("/api/v1/ee/license")).status_code == 403


@pytest.mark.asyncio
async def test_community_build_exposes_no_ee_routes(monkeypatch):
    """With register_ee unavailable (Community image), /api/v1/ee/* must not exist."""
    import app.main as main_mod

    monkeypatch.setattr(main_mod, "_mount_web_ui", lambda app: None)
    orig_import = __import__

    def _no_ee(name, *a, **k):
        if name == "app.ee" or name.startswith("app.ee."):
            raise ModuleNotFoundError(name)
        return orig_import(name, *a, **k)

    monkeypatch.setattr("builtins.__import__", _no_ee)
    app = main_mod.create_app()
    monkeypatch.undo()
    paths = {getattr(r, "path", "") for r in app.routes}
    assert not any(p.startswith("/api/v1/ee") for p in paths)
