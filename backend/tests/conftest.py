"""Test fixtures. Uses an isolated SQLite database per test session and drives the
real ASGI app through httpx so transport + middleware + domain are all exercised.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

# CI can point the suite at a real PostgreSQL by exporting TESQIVO_TEST_DB_URL.
os.environ.setdefault(
    "TESQIVO_DB_URL",
    os.environ.get("TESQIVO_TEST_DB_URL", "sqlite+aiosqlite:///./.pytest_tesqivo.db"),
)
os.environ.setdefault("TESQIVO_REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("TESQIVO_SECRET_KEY", "test-secret-key-that-is-definitely-long-enough-xx")
os.environ.setdefault("TESQIVO_PUBLIC_URL", "http://testserver")
# Forced (not setdefault): the fixtures below send this exact token, so an ambient
# TESQIVO_BOOTSTRAP_TOKEN (e.g. from a CI job env) must not win.
os.environ["TESQIVO_BOOTSTRAP_TOKEN"] = "test-bootstrap-token"
os.environ["TESQIVO_ENVIRONMENT"] = "test"
os.environ.setdefault("TESQIVO_ARGON2_TIME_COST", "1")
os.environ.setdefault("TESQIVO_ARGON2_MEMORY_COST_KIB", "8192")
os.environ.setdefault("TESQIVO_ARGON2_PARALLELISM", "1")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import Base, get_engine, reset_engine_for_tests
from app.main import create_app

DB_FILE = "./.pytest_tesqivo.db"


@pytest_asyncio.fixture(scope="function")
async def app():
    is_sqlite = get_settings_url().startswith("sqlite")
    if is_sqlite:
        for f in (DB_FILE, DB_FILE + "-shm", DB_FILE + "-wal"):
            try:
                os.remove(f)
            except FileNotFoundError:
                pass
    reset_engine_for_tests()
    engine = get_engine()
    async with engine.begin() as conn:
        if not is_sqlite:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    application = create_app()
    yield application
    async with engine.begin() as conn:
        if not is_sqlite:
            await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def get_settings_url() -> str:
    from app.core.config import get_settings

    return get_settings().db_url


@pytest_asyncio.fixture(scope="function")
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


class ApiClient:
    """Thin wrapper that carries the session cookie + CSRF header automatically."""

    def __init__(self, client: AsyncClient):
        self._c = client
        self._csrf: str | None = None

    async def login(self, username: str, password: str) -> dict:
        r = await self._c.post(
            "/api/v1/auth/session", json={"username": username, "password": password}
        )
        r.raise_for_status()
        self._csrf = r.cookies.get("tesqivo_csrf") or self._c.cookies.get("tesqivo_csrf")
        return r.json()

    def _headers(self, extra: dict | None = None) -> dict:
        h = {"X-Tesqivo-Client": "web"}
        if self._csrf:
            h["X-CSRF-Token"] = self._csrf
        if extra:
            h.update(extra)
        return h

    async def get(self, url, **kw):
        return await self._c.get(url, headers=self._headers(kw.pop("headers", None)), **kw)

    async def post(self, url, **kw):
        return await self._c.post(url, headers=self._headers(kw.pop("headers", None)), **kw)

    async def put(self, url, **kw):
        return await self._c.put(url, headers=self._headers(kw.pop("headers", None)), **kw)

    async def patch(self, url, **kw):
        return await self._c.patch(url, headers=self._headers(kw.pop("headers", None)), **kw)

    async def delete(self, url, **kw):
        return await self._c.delete(url, headers=self._headers(kw.pop("headers", None)), **kw)


@pytest_asyncio.fixture
async def api(client) -> ApiClient:
    return ApiClient(client)


@pytest_asyncio.fixture
async def admin(client, api) -> ApiClient:
    """Completed first-admin setup, logged in."""
    r = await client.post(
        "/api/v1/setup",
        json={
            "username": "admin",
            "email": "admin@example.com",
            "display_name": "Admin",
            "password": "AdminPassw0rd!",
        },
        headers={"X-Bootstrap-Token": "test-bootstrap-token"},
    )
    assert r.status_code == 201, r.text
    await api.login("admin", "AdminPassw0rd!")
    return api


@pytest_asyncio.fixture
async def make_user(app, admin):
    """Factory: create an instance user and return a logged-in independent ApiClient."""
    transports: list = []

    async def _make(username: str, password: str = "MemberPass0!", is_system_admin: bool = False) -> ApiClient:
        r = await admin.post(
            "/api/v1/users",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "display_name": username.title(),
                "password": password,
                "is_system_admin": is_system_admin,
            },
        )
        assert r.status_code == 201, r.text
        transport = ASGITransport(app=app)
        c = AsyncClient(transport=transport, base_url="http://testserver")
        transports.append(c)
        wrapper = ApiClient(c)
        await wrapper.login(username, password)
        wrapper.user_id = r.json()["id"]  # type: ignore[attr-defined]
        return wrapper

    yield _make
    for c in transports:
        await c.aclose()


@pytest_asyncio.fixture
async def project(admin) -> dict:
    r = await admin.post(
        "/api/v1/projects", json={"key": "DEMO", "name": "Demo Project"}
    )
    assert r.status_code == 201, r.text
    return r.json()


def uid() -> str:
    return str(uuid.uuid4())
