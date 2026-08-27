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
async def test_error_envelope_shape(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401
    body = r.json()
    assert set(body["error"]) >= {"code", "message", "status", "correlation_id", "retryable"}
    assert body["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert r.headers["X-Correlation-ID"]
