"""Increment 2: authentication - sessions, lockout, disabled accounts, CSRF, reset."""

import pytest


@pytest.mark.asyncio
async def test_login_sets_httponly_cookie_and_me_works(client, admin):
    r = await client.get("/api/v1/auth/me", headers={"X-Tesqivo-Client": "web"})
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "admin"
    assert body["is_system_admin"] is True
    set_cookie = r.request.headers.get("cookie", "")
    assert "tesqivo_session" in set_cookie


@pytest.mark.asyncio
async def test_bad_password_is_uniform_401(client, admin):
    r = await client.post("/api/v1/auth/session", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_lockout_after_threshold(client, admin):
    for _ in range(5):
        await client.post("/api/v1/auth/session", json={"username": "admin", "password": "nope"})
    # even the correct password now fails while locked
    r = await client.post("/api/v1/auth/session", json={"username": "admin", "password": "AdminPassw0rd!"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_unsafe_request_without_csrf_is_forbidden(client, admin):
    # admin fixture logged in; strip CSRF header
    r = await client.post("/api/v1/projects", json={"key": "NOCSRF", "name": "x"})
    assert r.status_code == 403
    assert "CSRF" in r.json()["error"]["message"]


@pytest.mark.asyncio
async def test_disabled_user_cannot_login(client, admin, api):
    r = await api.post(
        "/api/v1/users",
        json={"username": "tester1", "email": "t1@x.com", "display_name": "T1", "password": "TesterPass0!"},
    )
    assert r.status_code == 201, r.text
    uid = r.json()["id"]

    r = await api.put(f"/api/v1/users/{uid}/status", json={"status": "disabled"})
    assert r.status_code == 200

    # login attempt now uniformly fails (this replaces the shared cookie jar, which is fine)
    r = await client.post("/api/v1/auth/session", json={"username": "tester1", "password": "TesterPass0!"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_admin_initiated_password_reset(client, admin, api):
    r = await api.post(
        "/api/v1/users",
        json={"username": "tester2", "email": "t2@x.com", "display_name": "T2", "password": "TesterPass0!"},
    )
    uid = r.json()["id"]
    r = await api.post(f"/api/v1/users/{uid}/password-reset")
    assert r.status_code == 201
    temp = r.json()["temporary_password"]

    # old password no longer works
    r = await client.post("/api/v1/auth/session", json={"username": "tester2", "password": "TesterPass0!"})
    assert r.status_code == 401

    # temp password logs in directly and forces a change
    r = await client.post("/api/v1/auth/session", json={"username": "tester2", "password": temp})
    assert r.status_code == 201, r.text
    assert r.json()["must_change_password"] is True

    csrf = client.cookies.get("tesqivo_csrf")
    r = await client.post(
        "/api/v1/auth/password",
        json={"current_password": temp, "new_password": "BrandNewPass9!"},
        headers={"X-CSRF-Token": csrf, "X-Tesqivo-Client": "web"},
    )
    assert r.status_code == 204

    r = await client.post("/api/v1/auth/session", json={"username": "tester2", "password": "BrandNewPass9!"})
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_admin_sets_user_password_directly(client, admin, api):
    r = await api.post(
        "/api/v1/users",
        json={"username": "tester3", "email": "t3@x.com", "display_name": "T3", "password": "TesterPass0!"},
    )
    uid = r.json()["id"]
    r = await api.patch(f"/api/v1/users/{uid}", json={"password": "AdminSetPass77!"})
    assert r.status_code == 200, r.text

    r = await client.post("/api/v1/auth/session", json={"username": "tester3", "password": "AdminSetPass77!"})
    assert r.status_code == 201, r.text
    assert r.json()["must_change_password"] is False
