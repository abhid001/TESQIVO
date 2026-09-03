"""Code-review fixes: server-side forced-password-change, hashed session tokens,
session revocation on password change, logout CSRF, shared identity validation."""

from hashlib import sha256

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.core.identity import identity_errors
from app.models import UserSession
from tests.conftest import ApiClient

# ---------------------------------------------------------------- finding #1

@pytest.mark.asyncio
async def test_must_change_password_is_enforced_server_side(app, admin, make_user):
    u = await make_user("mcp")
    reset = await admin.post(f"/api/v1/users/{u.user_id}/password-reset")
    temp = reset.json()["temporary_password"]

    victim = ApiClient(AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver"))
    await victim.login("mcp", temp)

    # allowed while must_change_password is set
    assert (await victim.get("/api/v1/auth/me")).status_code == 200
    # everything else is blocked
    blocked = await victim.get("/api/v1/projects")
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"

    # after changing it, normal access resumes
    ch = await victim.post(
        "/api/v1/auth/password",
        json={"current_password": temp, "new_password": "Brand-New-Pass9!"},
    )
    assert ch.status_code == 204
    assert (await victim.get("/api/v1/projects")).status_code == 200


# ---------------------------------------------------------------- finding #5

@pytest.mark.asyncio
async def test_session_token_is_stored_hashed(admin):
    cookie = admin._c.cookies.get("tesqivo_session")
    assert cookie
    sm = get_sessionmaker()
    async with sm() as s:
        rows = list(await s.scalars(select(UserSession)))
    stored = {r.token_id for r in rows}
    assert cookie not in stored
    assert sha256(cookie.encode()).hexdigest() in stored


# ---------------------------------------------------------------- finding #10

@pytest.mark.asyncio
async def test_password_change_revokes_other_sessions_but_keeps_current(app, make_user):
    u1 = await make_user("multi")
    # a second, independent login for the same account
    u2 = ApiClient(AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver"))
    await u2.login("multi", "MemberPass0!")
    assert (await u2.get("/api/v1/auth/me")).status_code == 200

    ch = await u1.post(
        "/api/v1/auth/password",
        json={"current_password": "MemberPass0!", "new_password": "Rotated-Pass-1!"},
    )
    assert ch.status_code == 204

    assert (await u1.get("/api/v1/auth/me")).status_code == 200          # current kept
    assert (await u2.get("/api/v1/auth/me")).status_code == 401          # other revoked
    await u2._c.aclose()


# ---------------------------------------------------------------- finding #11

@pytest.mark.asyncio
async def test_logout_requires_csrf(admin):
    raw = admin._c
    # no X-CSRF-Token header
    r = await raw.delete("/api/v1/auth/session", headers={"X-Tesqivo-Client": "web"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"
    # with it
    csrf = raw.cookies.get("tesqivo_csrf")
    ok = await raw.delete(
        "/api/v1/auth/session",
        headers={"X-Tesqivo-Client": "web", "X-CSRF-Token": csrf},
    )
    assert ok.status_code == 204


# ---------------------------------------------------------------- finding #12

def test_identity_errors_flags_bad_values():
    assert identity_errors(username="ab", email="x@y.z", display_name="A")  # too short
    assert identity_errors(username="ok_user", email="not-an-email", display_name="A")
    assert identity_errors(username="bad user!", email="x@y.z", display_name="A")
    assert identity_errors(username="good.user-1", email="a@b.co", display_name="Real Name") == []


@pytest.mark.asyncio
async def test_setup_rejects_a_malformed_email_with_a_clear_message(client):
    r = await client.post(
        "/api/v1/setup",
        json={"username": "root", "email": "nope", "display_name": "Root", "password": "Str0ng-Pass!!"},
        headers={"X-Bootstrap-Token": "test-bootstrap-token"},
    )
    assert r.status_code == 422
    assert "valid email" in r.json()["error"]["message"]
