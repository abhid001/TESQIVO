"""Small operational CLI: `python -m app.cli <command>`."""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text

from app.core.db import get_sessionmaker


async def _wait_db(retries: int = 30) -> None:
    sm = get_sessionmaker()
    for i in range(retries):
        try:
            async with sm() as s:
                await s.execute(text("SELECT 1"))
            print("database reachable")
            return
        except Exception as exc:  # noqa: BLE001
            print(f"waiting for database ({i + 1}/{retries}): {exc}")
            await asyncio.sleep(2)
    sys.exit(1)


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python -m app.cli [wait-db]")
        sys.exit(2)
    cmd = sys.argv[1]
    if cmd == "wait-db":
        asyncio.run(_wait_db())
    else:
        print(f"unknown command: {cmd}")
        sys.exit(2)


if __name__ == "__main__":
    main()
