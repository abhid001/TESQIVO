"""Code-review fixes #3 (counter-init race) and #4 (membership re-add)."""

import asyncio
import os

import pytest

from app.core.config import get_settings

_IS_PG = get_settings().db_url.startswith("postgresql") or bool(os.environ.get("TESQIVO_TEST_DB_URL"))
pg_only = pytest.mark.skipif(not _IS_PG, reason="needs a real PostgreSQL for concurrency")


# ---------------------------------------------------------------- finding #4

@pytest.mark.asyncio
async def test_member_can_be_removed_added_and_removed_again(admin, project, make_user):
    u = await make_user("recycle")
    pid = project["id"]

    async def is_member() -> bool:
        r = await admin.get(f"/api/v1/projects/{pid}/members")
        return any(m["user_id"] == u.user_id and m["status"] == "active" for m in r.json())

    for _ in range(3):
        r = await admin.post(f"/api/v1/projects/{pid}/members", json={"user_id": u.user_id, "role": "tester"})
        assert r.status_code in (200, 201), r.text
        assert await is_member()

        r = await admin.delete(f"/api/v1/projects/{pid}/members/{u.user_id}")
        assert r.status_code == 204, r.text
        assert not await is_member()


# ---------------------------------------------------------------- finding #3

@pg_only
@pytest.mark.asyncio
async def test_concurrent_first_keys_do_not_collide(admin, project):
    from app.core.db import get_sessionmaker
    from app.domain.keys import next_key

    pid_str = project["id"]
    import uuid as _uuid

    pid = _uuid.UUID(pid_str)
    sm = get_sessionmaker()

    async def mint() -> str:
        async with sm() as s:
            async with s.begin():
                key = await next_key(s, pid, "requirement")
            return key

    keys = await asyncio.gather(*(mint() for _ in range(8)))
    seqs = sorted(int(k.rsplit("-", 1)[1]) for k in keys)
    assert seqs == list(range(1, 9)), keys
