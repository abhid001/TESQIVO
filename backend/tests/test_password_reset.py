"""Self-service forgot-password flow (decision D-019)."""

import pytest

from app.core.config import Settings, get_settings
from app.core.mailer import CapturingMailer, set_mailer_for_tests


@pytest.fixture
def email_off():
    set_mailer_for_tests(None)
    yield
    set_mailer_for_tests(None)


@pytest.fixture
def email_on(monkeypatch):
    monkeypatch.setattr(Settings, "email_enabled", property(lambda self: True))
    box = CapturingMailer()
    set_mailer_for_tests(box)
    yield box
    set_mailer_for_tests(None)


@pytest.mark.asyncio
async def test_request_when_email_not_configured_points_to_admin(client, admin, email_off):
    await admin.post(
        "/api/v1/users",
        json={"username": "normaluser", "email": "n@example.com", "display_name": "N", "password": "NormalPass01!"},
    )
    r = await client.post("/api/v1/auth/password-reset/request", json={"identifier": "normaluser"})
    assert r.status_code == 200
    body = r.json()
    assert body["outcome"] == "email_unavailable"
    assert "administrator" in body["message"].lower()
    assert body["email_configured"] is False


@pytest.mark.asyncio
async def test_admin_account_always_contact_maintainer(client, admin, email_on):
    r = await client.post("/api/v1/auth/password-reset/request", json={"identifier": "admin"})
    assert r.status_code == 200
    body = r.json()
    assert body["outcome"] == "contact_maintainer"
    assert "maintain" in body["message"].lower()
    assert email_on.outbox == []  # admins are never emailed a temp password


@pytest.mark.asyncio
def _token_from(body: str) -> str:
    import re

    m = re.search(r"[?&]token=([\w-]+)", body)
    assert m, body
    return m.group(1)


async def test_email_flow_sends_a_link_and_does_not_change_the_password(client, admin, email_on):
    r = await admin.post(
        "/api/v1/users",
        json={"username": "alice", "email": "alice@example.com", "display_name": "Alice", "password": "AlicePass01!"},
    )
    assert r.status_code == 201

    r = await client.post("/api/v1/auth/password-reset/request", json={"identifier": "alice@example.com"})
    assert r.json()["outcome"] == "email_sent"
    assert len(email_on.outbox) == 1
    msg = email_on.outbox[0]
    assert msg["to"] == "alice@example.com"
    assert "/reset?token=" in msg["body"]
    token = _token_from(msg["body"])

    # the current password STILL works - nothing changed yet (finding #2)
    r = await client.post("/api/v1/auth/session", json={"username": "alice", "password": "AlicePass01!"})
    assert r.status_code == 201

    # redeem the link
    r = await client.post(
        "/api/v1/auth/password-reset/complete",
        json={"token": token, "new_password": "AliceBrandNew1!"},
    )
    assert r.status_code == 204

    # now the old password is dead and the new one works
    assert (await client.post("/api/v1/auth/session", json={"username": "alice", "password": "AlicePass01!"})).status_code == 401
    assert (await client.post("/api/v1/auth/session", json={"username": "alice", "password": "AliceBrandNew1!"})).status_code == 201

    # the link is single-use
    r = await client.post(
        "/api/v1/auth/password-reset/complete",
        json={"token": token, "new_password": "AnotherOne99!"},
    )
    assert r.status_code == 401


async def test_reset_link_still_generic_and_password_intact_when_mail_fails(client, admin, monkeypatch):
    from app.core.mailer import set_mailer_for_tests

    r = await admin.post(
        "/api/v1/users",
        json={"username": "bob", "email": "bob@example.com", "display_name": "Bob", "password": "BobsPass012!"},
    )
    assert r.status_code == 201

    monkeypatch.setattr(Settings, "email_enabled", property(lambda self: True))

    class _Boom:
        async def send(self, **_):
            raise RuntimeError("smtp down")

    set_mailer_for_tests(_Boom())
    try:
        r = await client.post("/api/v1/auth/password-reset/request", json={"identifier": "bob"})
        assert r.status_code == 200
        assert r.json()["outcome"] == "email_sent"  # unchanged, no disclosure
        # password is untouched despite the mail failure
        assert (await client.post("/api/v1/auth/session", json={"username": "bob", "password": "BobsPass012!"})).status_code == 201
    finally:
        set_mailer_for_tests(None)


@pytest.mark.asyncio
async def test_unknown_identifier_is_generic_and_sends_nothing(client, admin, email_on):
    r = await client.post("/api/v1/auth/password-reset/request", json={"identifier": "ghost@nowhere.test"})
    assert r.json()["outcome"] == "email_sent"  # same message, no disclosure
    assert email_on.outbox == []


@pytest.mark.asyncio
async def test_change_password_rejects_wrong_current_and_reuse(client, admin):
    csrf = client.cookies.get("tesqivo_csrf")
    h = {"X-CSRF-Token": csrf, "X-Tesqivo-Client": "web"}
    r = await client.post(
        "/api/v1/auth/password",
        json={"current_password": "wrong", "new_password": "SomethingNew12!"},
        headers=h,
    )
    assert r.status_code == 401

    r = await client.post(
        "/api/v1/auth/password",
        json={"current_password": "AdminPassw0rd!", "new_password": "AdminPassw0rd!"},
        headers=h,
    )
    assert r.status_code == 422


def test_settings_email_disabled_by_default():
    get_settings.cache_clear()
    assert Settings(  # type: ignore[call-arg]
        db_url="sqlite+aiosqlite://", redis_url="redis://x", secret_key="x" * 32,
        public_url="http://x",
    ).email_enabled is False
