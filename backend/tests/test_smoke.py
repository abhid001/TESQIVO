"""Increment 1: deployable shell - health, OpenAPI, setup gate."""

import pytest


@pytest.mark.asyncio
async def test_healthz(client):
    r = await client.get("/api/v1/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readyz(client):
    r = await client.get("/api/v1/readyz")
    assert r.status_code == 200
    assert r.json()["checks"]["database"] == "ok"


@pytest.mark.asyncio
async def test_openapi_document_is_generated(client):
    r = await client.get("/api/v1/openapi.json")
    assert r.status_code == 200
    doc = r.json()
    assert doc["info"]["title"] == "TESQIVO API"
    assert "/api/v1/projects/{project_id}/reports/summary" in doc["paths"]


@pytest.mark.asyncio
async def test_setup_status_and_gate(client):
    r = await client.get("/api/v1/setup/status")
    assert r.json() == {"needs_setup": True}

    # wrong bootstrap token -> forbidden
    r = await client.post(
        "/api/v1/setup",
        json={"username": "someone", "email": "a@x.com", "display_name": "A", "password": "LongPassw0rd!"},
        headers={"X-Bootstrap-Token": "wrong"},
    )
    assert r.status_code == 403

    r = await client.post(
        "/api/v1/setup",
        json={"username": "admin", "email": "admin@x.com", "display_name": "Admin", "password": "AdminPassw0rd!"},
        headers={"X-Bootstrap-Token": "test-bootstrap-token"},
    )
    assert r.status_code == 201

    # second attempt rejected
    r = await client.post(
        "/api/v1/setup",
        json={"username": "second", "email": "b@x.com", "display_name": "B", "password": "AnotherPass0!"},
        headers={"X-Bootstrap-Token": "test-bootstrap-token"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "SETUP_ALREADY_COMPLETED"


@pytest.mark.asyncio
async def test_version_endpoint(client):
    r = await client.get("/api/v1/version")
    assert r.status_code == 200
    body = r.json()
    assert body["version"]
    assert body["environment"] == "test"


@pytest.mark.asyncio
async def test_spa_is_served_when_static_dir_is_configured(tmp_path, monkeypatch):
    from httpx import ASGITransport, AsyncClient

    from app.core.config import get_settings
    from app.main import create_app

    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text('<!doctype html><html><body><div id="root"></div></body></html>')
    (static / "assets" / "app.js").write_text("console.log(1)")

    monkeypatch.setenv("TESQIVO_STATIC_DIR", str(static))
    get_settings.cache_clear()
    try:
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            root = await c.get("/")
            assert root.status_code == 200 and '<div id="root">' in root.text
            # client-side route falls back to index.html
            deep = await c.get("/p/DEMO/dashboard")
            assert deep.status_code == 200 and deep.text.startswith("<!doctype html>")
            # a real static file is served
            assert (await c.get("/assets/app.js")).status_code == 200
            # the API still wins and unknown API paths still 404 as JSON
            assert (await c.get("/api/v1/healthz")).json() == {"status": "ok"}
            missing = await c.get("/api/v1/nope")
            assert missing.status_code == 404 and missing.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_error_envelope_shape(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401
    body = r.json()
    assert set(body["error"]) >= {"code", "message", "status", "correlation_id", "retryable"}
    assert body["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert r.headers["X-Correlation-ID"]
